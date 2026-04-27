import { useEffect, useState } from 'react';
import { storageService, Favorite } from '../services/storageService';

export default function FavoritesScreen() {
  const [favorites, setFavorites] = useState<Favorite[]>([]);

  useEffect(() => {
    const loadFavorites = async () => {
      const faves = await storageService.getFavorites();
      setFavorites(faves);
    };

    loadFavorites();
  }, []);

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '24px', marginBottom: '16px' }}>즐겨찾기</h1>
      {favorites.length === 0 ? (
        <p style={{ fontSize: '14px', color: 'var(--c-mid)' }}>
          즐겨찾기한 분양공고가 없습니다.
        </p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>
          {favorites.map(favorite => (
            <div
              key={favorite.post_id}
              style={{
                backgroundColor: 'var(--c-surface)',
                borderRadius: '8px',
                padding: '16px',
                border: '1px solid var(--c-light-gray)',
              }}
            >
              <p style={{ fontSize: '14px', fontWeight: '500' }}>
                {favorite.post_id}
              </p>
              <p style={{ fontSize: '12px', color: 'var(--c-mid)' }}>
                {new Date(favorite.added_at).toLocaleDateString('ko-KR')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
