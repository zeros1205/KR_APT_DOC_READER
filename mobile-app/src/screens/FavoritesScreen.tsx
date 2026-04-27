import { useEffect, useState } from 'react';
import { storageService, Favorite } from '../services/storageService';
import PostDetailScreen from './PostDetailScreen';

export default function FavoritesScreen() {
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'recent' | 'date'>('recent');

  useEffect(() => {
    loadFavorites();
  }, []);

  const loadFavorites = async () => {
    const faves = await storageService.getFavorites();
    setFavorites(faves);
  };

  const handleRemoveFavorite = async (postId: string) => {
    await storageService.removeFavorite(postId);
    setFavorites(prev => prev.filter(f => f.post_id !== postId));
  };

  const sortedFavorites = [...favorites].sort((a, b) => {
    if (sortBy === 'recent') {
      return new Date(b.added_at).getTime() - new Date(a.added_at).getTime();
    }
    return new Date(b.added_at).getTime() - new Date(a.added_at).getTime();
  });

  const filteredFavorites = sortedFavorites.filter(fav =>
    fav.post_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (selectedPostId) {
    return (
      <PostDetailScreen
        postId={selectedPostId}
        onBack={() => setSelectedPostId(null)}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      <div style={{ padding: '24px', paddingBottom: '16px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '16px' }}>
          즐겨찾기
        </h1>

        <input
          type="text"
          placeholder="포스트 ID 검색..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            width: '100%',
            padding: '12px 16px',
            borderRadius: '8px',
            border: '1px solid var(--c-light-gray)',
            fontSize: '14px',
            backgroundColor: 'var(--c-surface)',
            color: 'var(--c-dark)',
            fontFamily: 'inherit',
            marginBottom: '12px',
          }}
        />

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setSortBy('recent')}
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: sortBy === 'recent' ? 'var(--c-primary)' : 'var(--c-light-gray)',
              color: sortBy === 'recent' ? '#ffffff' : 'var(--c-dark)',
              border: 'none',
              fontSize: '13px',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            최근 추가순
          </button>
          <button
            onClick={() => setSortBy('date')}
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: sortBy === 'date' ? 'var(--c-primary)' : 'var(--c-light-gray)',
              color: sortBy === 'date' ? '#ffffff' : 'var(--c-dark)',
              border: 'none',
              fontSize: '13px',
              fontWeight: '600',
              cursor: 'pointer',
            }}
          >
            추가 날짜순
          </button>
        </div>
      </div>

      <div style={{ flex: 1, padding: '0 24px 24px 24px', overflowY: 'auto' }}>
        {favorites.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: '60px', color: 'var(--c-mid)' }}>
            <p style={{ fontSize: '14px' }}>즐겨찾기한 분양공고가 없습니다</p>
          </div>
        ) : filteredFavorites.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: '40px', color: 'var(--c-mid)' }}>
            <p style={{ fontSize: '14px' }}>검색 결과가 없습니다</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px' }}>
            {filteredFavorites.map(favorite => (
              <div
                key={favorite.post_id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  backgroundColor: 'var(--c-surface)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  border: '1px solid var(--c-light-gray)',
                }}
              >
                <button
                  onClick={() => setSelectedPostId(favorite.post_id)}
                  style={{
                    flex: 1,
                    textAlign: 'left',
                    backgroundColor: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  <p style={{ fontSize: '14px', fontWeight: '500', color: 'var(--c-dark)', margin: 0 }}>
                    {favorite.post_id}
                  </p>
                  <p style={{ fontSize: '12px', color: 'var(--c-mid)', margin: '4px 0 0 0' }}>
                    {new Date(favorite.added_at).toLocaleDateString('ko-KR')}
                  </p>
                </button>
                <button
                  onClick={() => handleRemoveFavorite(favorite.post_id)}
                  style={{
                    backgroundColor: '#ff6b6b',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '6px 12px',
                    fontSize: '12px',
                    fontWeight: '600',
                    cursor: 'pointer',
                    marginLeft: '12px',
                    flexShrink: 0,
                  }}
                >
                  삭제
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
