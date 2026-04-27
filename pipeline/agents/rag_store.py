"""
rag_store.py
────────────────────────────────────────────────────
ChromaDB 기반 Vector DB 구성 및 RAG 검색

구조:
  - Collection: apartment_notices
  - Embedding: ChromaDB 기본 embedding
  - 청크 분할: 섹션별 (기본정보 / 자격조건 / 금융 / 입지)
────────────────────────────────────────────────────
"""

import sys
import re
from pathlib import Path
from dataclasses import dataclass

import chromadb

sys.path.append(str(Path(__file__).parent.parent))
from config import CHROMA_DIR
from agents.collector import NoticeDocument


# ──────────────────────────────────────────────────
# 청크 분할 전략
# ──────────────────────────────────────────────────

@dataclass
class Chunk:
    """단일 텍스트 청크"""
    text: str
    metadata: dict


def _split_into_chunks(doc: NoticeDocument) -> list[Chunk]:
    """
    공고문을 섹션별 청크로 분할

    섹션 패턴에 맞게 분할하고, 각 청크에 메타데이터 태깅
    작은 섹션은 합쳐서 최소 200자 이상 유지
    """
    base_meta = {
        "notice_id": doc.notice_id,
        "apt_name": doc.apt_name,
        "region": doc.region,
        "supply_date": doc.supply_date,
    }

    chunks = []
    text = doc.raw_text

    # 섹션 키워드로 분할
    section_patterns = [
        ("기본정보", r"(단지명|공급위치|공급규모|총공급)"),
        ("청약일정", r"(청약접수|당첨자|계약|입주예정)"),
        ("분양가", r"(분양가|평단가|가격|타입|㎡|세대)"),
        ("자격조건", r"(특별공급|신혼부부|생애최초|다자녀|노부모|일반공급|1순위|2순위|가점)"),
        ("금융", r"(중도금|잔금|계약금|대출|이자|무이자|집단대출|DSR|DTI)"),
        ("제한사항", r"(전매제한|실거주|투기과열|거주의무|재당첨)"),
        ("입지", r"(지하철|역|학교|초등|중학|상권|대형마트|병원|도보|차량)"),
    ]

    # 전체 텍스트를 줄 단위로 읽으며 섹션 분류
    section_lines: dict[str, list[str]] = {name: [] for name, _ in section_patterns}
    section_lines["기타"] = []

    for line in text.split("\n"):
        matched = False
        for section_name, pattern in section_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                section_lines[section_name].append(line)
                matched = True
                break
        if not matched:
            section_lines["기타"].append(line)

    # 청크 생성 (최소 길이 미달 시 "기타"에 합산)
    for section_name, lines in section_lines.items():
        section_text = "\n".join(lines).strip()
        if len(section_text) < 50:
            continue
        chunks.append(Chunk(
            text=f"[{section_name}]\n{section_text}",
            metadata={**base_meta, "section": section_name},
        ))

    # 표 데이터 청크 (각 표를 별도 청크)
    for i, table in enumerate(doc.tables):
        rows = [" | ".join(str(c) for c in row) for row in table]
        table_text = "\n".join(rows)
        if len(table_text) > 20:
            chunks.append(Chunk(
                text=f"[표_{i+1}]\n{table_text}",
                metadata={**base_meta, "section": f"표_{i+1}", "is_table": "true"},
            ))

    # 청크가 너무 없으면 전체 텍스트를 1500자 단위로 분할
    if len(chunks) < 2:
        for i in range(0, len(text), 1500):
            chunk_text = text[i:i+1500].strip()
            if chunk_text:
                chunks.append(Chunk(
                    text=chunk_text,
                    metadata={**base_meta, "section": f"chunk_{i//1500}"},
                ))

    return chunks


# ──────────────────────────────────────────────────
# ChromaDB 클라이언트
# ──────────────────────────────────────────────────

class ApartmentRAGStore:
    """
    아파트 분양 공고 Vector DB

    사용법:
        store = ApartmentRAGStore()
        store.add_notice(doc)
        results = store.search("중도금 대출 조건", notice_id="2026-001")
    """

    COLLECTION_NAME = "apartment_notices"

    def __init__(self, persist_dir: Path = CHROMA_DIR):
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(persist_dir))

        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        count = self.collection.count()
        print(f"  [RAG] ChromaDB 초기화 완료 (기존 {count}개 청크)")

    def add_notice(self, doc: NoticeDocument, overwrite: bool = True) -> int:
        """
        공고문을 Vector DB에 추가

        Args:
            doc: NoticeDocument 객체
            overwrite: 동일 notice_id 존재 시 덮어쓰기

        Returns:
            추가된 청크 수
        """
        # 기존 데이터 삭제 (덮어쓰기)
        if overwrite:
            existing = self.collection.get(
                where={"notice_id": doc.notice_id},
                include=[],
            )
            if existing["ids"]:
                self.collection.delete(where={"notice_id": doc.notice_id})
                print(f"  [RAG] 기존 데이터 삭제: {doc.notice_id} ({len(existing['ids'])}개)")

        # 청크 분할
        chunks = _split_into_chunks(doc)

        if not chunks:
            print(f"  [RAG] 청크 없음: {doc.apt_name}")
            return 0

        # 배치 추가
        ids = [f"{doc.notice_id}__chunk_{i}" for i in range(len(chunks))]
        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]

        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
        )

        print(f"  [RAG] 추가 완료: {doc.apt_name} ({len(chunks)}개 청크)")
        return len(chunks)

    def search(
        self,
        query: str,
        notice_id: str | None = None,
        n_results: int = 5,
        section_filter: str | None = None,
    ) -> list[dict]:
        """
        유사도 검색

        Args:
            query: 검색 쿼리
            notice_id: 특정 공고로 범위 제한 (None이면 전체)
            n_results: 반환 결과 수
            section_filter: 특정 섹션만 검색 (예: "금융", "자격조건")

        Returns:
            [{text, metadata, distance}, ...] 리스트
        """
        where = {}
        if notice_id:
            where["notice_id"] = notice_id
        if section_filter:
            where["section"] = section_filter

        kwargs: dict = {
            "query_texts": [query],
            "n_results": min(n_results, self.collection.count() or 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        try:
            results = self.collection.query(**kwargs)
        except Exception as e:
            print(f"  [RAG] 검색 실패: {e}")
            return []

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for text, meta, dist in zip(docs, metas, dists):
            output.append({
                "text": text,
                "metadata": meta,
                "distance": dist,
                "relevance": round(1 - dist, 3),  # 코사인 유사도
            })

        return output

    def get_full_context(self, notice_id: str) -> str:
        """
        특정 공고의 전체 청크를 하나의 컨텍스트 문자열로 반환
        (Agent 1 팩트 추출용)
        """
        results = self.collection.get(
            where={"notice_id": notice_id},
            include=["documents", "metadatas"],
        )
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        if not metas:
            return ""

        # 메타데이터에서 기본 정보 추출
        first_meta = metas[0]
        apt_name = first_meta.get("apt_name", "")
        region = first_meta.get("region", "")
        supply_date = first_meta.get("supply_date", "")

        # 기본 정보 헤더 생성 (Agent 1이 apt_name을 추출할 수 있도록)
        header_parts = []
        if apt_name:
            header_parts.append(f"【단지명】\n{apt_name}")
        if region:
            header_parts.append(f"【지역】\n{region}")
        if supply_date:
            header_parts.append(f"【공급일】\n{supply_date}")

        # 섹션 순서대로 정렬
        SECTION_ORDER = ["기본정보", "청약일정", "분양가", "자격조건", "금융", "제한사항", "입지", "기타"]
        sorted_pairs = sorted(
            zip(metas, docs),
            key=lambda x: SECTION_ORDER.index(x[0].get("section", "기타"))
            if x[0].get("section", "기타") in SECTION_ORDER else 99
        )

        context_parts = header_parts + [doc for _, doc in sorted_pairs]
        return "\n\n".join(context_parts)

    def list_notices(self) -> list[dict]:
        """저장된 공고 목록 조회"""
        if self.collection.count() == 0:
            return []

        results = self.collection.get(include=["metadatas"])
        seen_ids = set()
        notices = []
        for meta in results.get("metadatas", []):
            nid = meta.get("notice_id")
            if nid and nid not in seen_ids:
                seen_ids.add(nid)
                notices.append({
                    "notice_id": nid,
                    "apt_name": meta.get("apt_name", ""),
                    "region": meta.get("region", ""),
                    "supply_date": meta.get("supply_date", ""),
                })
        return notices

    def delete_notice(self, notice_id: str) -> None:
        """공고 삭제"""
        self.collection.delete(where={"notice_id": notice_id})
        print(f"  [RAG] 삭제 완료: {notice_id}")


# ──────────────────────────────────────────────────
# 단독 실행 테스트
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from pipeline.agents.collector import get_sample_document

    print("=" * 50)
    print("RAG Store 테스트 (샘플 공고)")
    print("=" * 50)

    doc = get_sample_document()
    store = ApartmentRAGStore()

    # 추가
    n = store.add_notice(doc)
    print(f"청크 {n}개 추가")

    # 검색 테스트
    queries = [
        "중도금 대출 가능한가요",
        "1순위 청약 접수일",
        "타입별 분양가",
    ]
    for q in queries:
        results = store.search(q, notice_id=doc.notice_id, n_results=2)
        print(f"\n쿼리: '{q}'")
        for r in results:
            print(f"  [{r['relevance']:.2f}] {r['text'][:80]}...")

    # 전체 컨텍스트
    ctx = store.get_full_context(doc.notice_id)
    print(f"\n전체 컨텍스트 길이: {len(ctx)}자")
