import { useEffect, useState } from 'react';
import { apiService, PostMeta } from '../services/apiService';
import { storageService } from '../services/storageService';

export default function HomeScreen() {
  const [posts, setPosts] = useState<PostMeta[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadPosts = async () => {
      try {
        setIsLoading(true);
        const prefs = await storageService.getUserPreferences();
        const data = await apiService.getPosts(
          prefs.regions.length > 0 ? prefs.regions : undefined,
          10,
          0
        );
        setPosts(data.posts);
      } catch (err) {
        setError('포스트를 불러올 수 없습니다');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    loadPosts();
  }, []);

  if (isLoading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <p>로딩 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--c-mid)' }}>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '24px', marginBottom: '16px' }}>분양공고</h1>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>
        {posts.map(post => (
          <div
            key={post.post_id}
            style={{
              backgroundColor: 'var(--c-surface)',
              borderRadius: '8px',
              padding: '16px',
              border: '1px solid var(--c-light-gray)',
            }}
          >
            <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>
              {post.apt_name}
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--c-mid)', marginBottom: '4px' }}>
              {post.region}
            </p>
            <p style={{ fontSize: '13px', color: 'var(--c-dark)' }}>
              {post.notice_date}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
