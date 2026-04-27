import axios, { AxiosInstance } from 'axios';
import { cacheService } from './cacheService';

interface PostMeta {
  post_id: string;
  apt_name: string;
  notice_date: string;
  region: string;
  price_min?: number;
  price_max?: number;
  thumbnail_url?: string;
}

interface PostDetail {
  post_id: string;
  apt_name: string;
  content: string;
  notice_date: string;
  region: string;
}

class ApiService {
  private api: AxiosInstance;
  private baseURL = 'https://apt-note.com/api';

  constructor() {
    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: 10000,
    });
  }

  async getPosts(
    regions?: string[],
    limit: number = 10,
    offset: number = 0
  ): Promise<{ posts: PostMeta[]; total: number }> {
    try {
      // 개발 환경: manifest.json 사용
      if (process.env.NODE_ENV === 'development') {
        const response = await fetch('/manifest.json');
        const data = await response.json();
        await cacheService.setManifest(data);

        let posts: PostMeta[] = data.posts;

        // 지역 필터링
        if (regions && regions.length > 0) {
          posts = posts.filter(p => regions.includes(p.region));
        }

        // 최신순 정렬
        posts = posts.sort(
          (a, b) =>
            new Date(b.notice_date).getTime() -
            new Date(a.notice_date).getTime()
        );

        // 페이지네이션
        const paginated = posts.slice(offset, offset + limit);

        return { posts: paginated, total: posts.length };
      }

      // 프로덕션 환경: API 호출
      const params: any = { limit, offset };
      if (regions && regions.length > 0) {
        params.regions = regions.join(',');
      }
      const response = await this.api.get('/posts', { params });
      await cacheService.setCachedPostsList(response.data.posts);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch posts:', error);

      // 오프라인 모드: 캐시된 데이터 반환
      if (!navigator.onLine) {
        cacheService.setOfflineMode(true);
        console.log('Offline mode: returning cached posts');
        const cached = await cacheService.getCachedPostsList();
        if (cached) {
          let posts = cached;
          if (regions && regions.length > 0) {
            posts = posts.filter(p => regions.includes(p.region));
          }
          const paginated = posts.slice(offset, offset + limit);
          return { posts: paginated, total: posts.length };
        }
      }

      throw error;
    }
  }

  async getPostDetail(postId: string): Promise<PostDetail> {
    try {
      // 개발 환경: 샘플 데이터 반환
      if (process.env.NODE_ENV === 'development') {
        const sampleContent = `
          <h2>아파트 상세 정보</h2>
          <p><strong>주소:</strong> 서울시 강남구 테헤란로 123</p>
          <p><strong>규모:</strong> 지상 40층, 총 500세대</p>
          <p><strong>분양가:</strong> 5억 ~ 15억원</p>
          <p><strong>입주 예정:</strong> 2027년 6월</p>

          <h3>특징</h3>
          <ul>
            <li>강남역 도보 5분 거리</li>
            <li>프리미엄 조경 및 편의시설</li>
            <li>에너지 효율 1등급</li>
            <li>스마트 홈 시스템 기본 설치</li>
          </ul>

          <h3>청약 일정</h3>
          <ul>
            <li>일반공급 1순위: 2026년 5월 1일 ~ 5월 5일</li>
            <li>일반공급 2순위: 2026년 5월 6일 ~ 5월 10일</li>
            <li>특별공급: 2026년 4월 28일 ~ 4월 30일</li>
          </ul>

          <p style="color: #666; font-size: 14px; margin-top: 20px;">
            ⚠️ 본 정보는 샘플 데이터입니다. 정확한 정보는 청약홈 공식사이트에서 확인하세요.
          </p>
        `;

        const detail: PostDetail = {
          post_id: postId,
          apt_name: '샘플 아파트',
          content: sampleContent,
          notice_date: new Date().toISOString().split('T')[0],
          region: '서울',
        };

        await cacheService.setCachedPost(postId, detail);
        return detail;
      }

      // 프로덕션 환경: API 호출
      const response = await this.api.get(`/posts/${postId}`);
      await cacheService.setCachedPost(postId, response.data);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch post ${postId}:`, error);

      // 오프라인 모드: 캐시된 데이터 반환
      if (!navigator.onLine) {
        cacheService.setOfflineMode(true);
        console.log(`Offline mode: returning cached post ${postId}`);
        const cached = await cacheService.getCachedPost(postId);
        if (cached) {
          return cached;
        }
      }

      throw error;
    }
  }

  async registerDevice(
    fcmToken: string,
    deviceId: string,
    platform: 'ios' | 'android'
  ): Promise<{ user_id: string; status: string }> {
    try {
      const response = await this.api.post('/users/register-device', {
        fcm_token: fcmToken,
        device_id: deviceId,
        platform,
      });
      return response.data;
    } catch (error) {
      console.error('Failed to register device:', error);
      throw error;
    }
  }

  async setUserInterests(userId: string, regions: string[]): Promise<any> {
    try {
      const response = await this.api.post(
        `/users/${userId}/interests`,
        { regions }
      );
      return response.data;
    } catch (error) {
      console.error('Failed to set user interests:', error);
      throw error;
    }
  }
}

export const apiService = new ApiService();
export type { PostMeta, PostDetail };
