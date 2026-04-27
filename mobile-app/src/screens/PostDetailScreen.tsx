import { useEffect, useState } from 'react';
import { apiService, PostDetail } from '../services/apiService';
import { cacheService } from '../services/cacheService';
import { storageService } from '../services/storageService';

interface PostDetailScreenProps {
  postId: string;
  onBack: () => void;
}

export default function PostDetailScreen({ postId, onBack }: PostDetailScreenProps) {
  const [post, setPost] = useState<PostDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);

  useEffect(() => {
    const loadPost = async () => {
      try {
        setIsLoading(true);

        let postData = await cacheService.getCachedPost(postId);

        if (!postData) {
          postData = await apiService.getPostDetail(postId);
          await cacheService.setCachedPost(postId, postData);
        }

        setPost(postData);

        const favorite = await storageService.isFavorite(postId);
        setIsFavorite(favorite);
      } catch (err) {
        setError('포스트를 불러올 수 없습니다');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    loadPost();
  }, [postId]);

  const handleFavoriteToggle = async () => {
    if (isFavorite) {
      await storageService.removeFavorite(postId);
      setIsFavorite(false);
    } else {
      await storageService.addFavorite(postId);
      setIsFavorite(true);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 24px',
          backgroundColor: 'var(--c-surface)',
          borderBottom: '1px solid var(--c-light-gray)',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <button
          onClick={onBack}
          style={{
            backgroundColor: 'transparent',
            border: 'none',
            fontSize: '24px',
            cursor: 'pointer',
          }}
        >
          ←
        </button>
        <h2 style={{ fontSize: '18px', fontWeight: '600', flex: 1, marginLeft: '12px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          상세 정보
        </h2>
        <button
          onClick={handleFavoriteToggle}
          style={{
            backgroundColor: isFavorite ? 'var(--c-primary)' : 'transparent',
            border: `2px solid ${isFavorite ? 'var(--c-primary)' : 'var(--c-light-gray)'}`,
            borderRadius: '8px',
            width: '40px',
            height: '40px',
            fontSize: '20px',
            cursor: 'pointer',
          }}
        >
          {isFavorite ? '⭐' : '☆'}
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
        {isLoading && (
          <div style={{ textAlign: 'center', padding: '40px 24px' }}>
            <p style={{ fontSize: '16px', color: 'var(--c-mid)' }}>로딩 중...</p>
          </div>
        )}

        {error && (
          <div style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--c-mid)' }}>
            <p>{error}</p>
          </div>
        )}

        {post && (
          <div>
            <h1 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px', color: 'var(--c-dark)' }}>
              {post.apt_name}
            </h1>

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                marginBottom: '24px',
                padding: '16px',
                backgroundColor: 'var(--c-primary-light)',
                borderRadius: '8px',
              }}
            >
              <p style={{ fontSize: '14px', color: 'var(--c-dark)', margin: 0 }}>
                <strong>📍 지역:</strong> {post.region}
              </p>
              <p style={{ fontSize: '14px', color: 'var(--c-dark)', margin: 0 }}>
                <strong>📅 공고일:</strong> {post.notice_date}
              </p>
            </div>

            <div style={{ backgroundColor: 'var(--c-surface)', borderRadius: '8px', padding: '16px', border: '1px solid var(--c-light-gray)' }}>
              <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', color: 'var(--c-dark)' }}>
                상세 정보
              </h3>
              <div
                style={{
                  fontSize: '14px',
                  lineHeight: '1.8',
                  color: 'var(--c-dark)',
                  wordBreak: 'break-word',
                }}
                dangerouslySetInnerHTML={{ __html: post.content }}
              />
            </div>

            <div style={{ padding: '24px 0', textAlign: 'center', fontSize: '13px', color: 'var(--c-mid)' }}>
              <p>더 자세한 정보는 청약홈 공식사이트에서 확인하세요</p>
              <a
                href="https://www.applyhome.co.kr"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-block',
                  marginTop: '12px',
                  padding: '12px 24px',
                  backgroundColor: 'var(--c-primary)',
                  color: '#ffffff',
                  borderRadius: '8px',
                  textDecoration: 'none',
                  fontSize: '14px',
                  fontWeight: '600',
                }}
              >
                청약홈 방문
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
