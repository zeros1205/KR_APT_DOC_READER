import { useEffect, useState, useRef } from 'react';
import { apiService, PostMeta } from '../services/apiService';
import { storageService } from '../services/storageService';
import PostCard from '../components/PostCard';
import PostDetailScreen from './PostDetailScreen';

export default function HomeScreen() {
  const [posts, setPosts] = useState<PostMeta[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadInitialPosts();
    loadFavorites();
  }, []);

  const loadInitialPosts = async () => {
    try {
      setIsLoading(true);
      const prefs = await storageService.getUserPreferences();
      const data = await apiService.getPosts(
        prefs.regions.length > 0 ? prefs.regions : undefined,
        10,
        0
      );
      setPosts(data.posts);
      setOffset(10);
      setHasMore(data.posts.length === 10);
    } catch (err) {
      setError('포스트를 불러올 수 없습니다');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMorePosts = async () => {
    if (!hasMore || isLoadingMore) return;

    try {
      setIsLoadingMore(true);
      const prefs = await storageService.getUserPreferences();
      const data = await apiService.getPosts(
        prefs.regions.length > 0 ? prefs.regions : undefined,
        10,
        offset
      );
      setPosts(prev => [...prev, ...data.posts]);
      setOffset(prev => prev + 10);
      setHasMore(data.posts.length === 10);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const loadFavorites = async () => {
    const favs = await storageService.getFavorites();
    setFavorites(new Set(favs.map(f => f.post_id)));
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const div = e.currentTarget;
    if (div.scrollHeight - div.scrollTop < 500 && hasMore && !isLoadingMore) {
      loadMorePosts();
    }
  };

  const filteredPosts = posts.filter(post =>
    post.apt_name.toLowerCase().includes(searchQuery.toLowerCase())
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
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflowY: 'auto',
        padding: '24px',
        gap: '16px',
      }}
    >
      <div>
        <h1 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '16px' }}>
          분양공고
        </h1>

        <input
          type="text"
          placeholder="단지명 검색..."
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
          }}
        />
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--c-mid)' }}>
          <p>로딩 중...</p>
        </div>
      ) : error ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--c-mid)' }}>
          <p>{error}</p>
        </div>
      ) : filteredPosts.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--c-mid)' }}>
          <p>검색 결과가 없습니다</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px' }}>
          {filteredPosts.map(post => (
            <PostCard
              key={post.post_id}
              post={post}
              onPress={(p) => setSelectedPostId(p.post_id)}
              isFavorite={favorites.has(post.post_id)}
              onFavoriteToggle={(postId, isFav) => {
                const newFavs = new Set(favorites);
                if (isFav) {
                  newFavs.add(postId);
                } else {
                  newFavs.delete(postId);
                }
                setFavorites(newFavs);
              }}
            />
          ))}
        </div>
      )}

      {isLoadingMore && (
        <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--c-mid)' }}>
          <p>더 불러오는 중...</p>
        </div>
      )}

      {!hasMore && filteredPosts.length > 0 && (
        <div style={{ textAlign: 'center', padding: '20px 0', fontSize: '13px', color: 'var(--c-mid)' }}>
          <p>모든 포스트를 로드했습니다</p>
        </div>
      )}
    </div>
  );
}
