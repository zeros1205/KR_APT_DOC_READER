import { PostMeta } from '../services/apiService';
import { storageService } from '../services/storageService';
import { useState, useEffect } from 'react';

interface PostCardProps {
  post: PostMeta;
  onPress: (post: PostMeta) => void;
  isFavorite?: boolean;
  onFavoriteToggle?: (postId: string, isFavorite: boolean) => void;
}

export default function PostCard({
  post,
  onPress,
  isFavorite = false,
  onFavoriteToggle,
}: PostCardProps) {
  const [favorite, setFavorite] = useState(isFavorite);

  const handleFavoriteClick = async (e: React.MouseEvent) => {
    e.stopPropagation();

    if (favorite) {
      await storageService.removeFavorite(post.post_id);
      setFavorite(false);
      onFavoriteToggle?.(post.post_id, false);
    } else {
      await storageService.addFavorite(post.post_id);
      setFavorite(true);
      onFavoriteToggle?.(post.post_id, true);
    }
  };

  const priceRange = post.price_min && post.price_max
    ? `${post.price_min.toLocaleString()}만원 ~ ${post.price_max.toLocaleString()}만원`
    : '가격 정보 미정';

  return (
    <button
      onClick={() => onPress(post)}
      style={{
        display: 'block',
        width: '100%',
        backgroundColor: 'var(--c-surface)',
        border: '1px solid var(--c-light-gray)',
        borderRadius: '12px',
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'all 200ms',
        textAlign: 'left',
        padding: 0,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
        (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.boxShadow = 'none';
        (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
      }}
    >
      <div style={{ padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3
              style={{
                fontSize: '16px',
                fontWeight: '600',
                color: 'var(--c-dark)',
                marginBottom: '8px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {post.apt_name}
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
              <p style={{ fontSize: '13px', color: 'var(--c-mid)', margin: 0 }}>
                📍 {post.region}
              </p>
              <p style={{ fontSize: '13px', color: 'var(--c-dark)', margin: 0 }}>
                💰 {priceRange}
              </p>
              <p style={{ fontSize: '12px', color: 'var(--c-mid)', margin: 0 }}>
                📅 {post.notice_date}
              </p>
            </div>
          </div>

          <button
            onClick={handleFavoriteClick}
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: favorite ? 'var(--c-primary)' : 'var(--c-light-gray)',
              border: 'none',
              fontSize: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            {favorite ? '⭐' : '☆'}
          </button>
        </div>
      </div>
    </button>
  );
}
