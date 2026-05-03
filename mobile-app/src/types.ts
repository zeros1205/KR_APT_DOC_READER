export type NoticeCard = {
  notice_id: string;
  apt_name: string;
  post_url: string;
  region: string;
  notice_date: string;
  winner_date?: string;
  index_action?: "detail" | "applyhome";
  notice_url?: string;
  html?: string;
};

export type FavoriteNotice = NoticeCard & {
  post_url: string;
  price_range?: string;
  saved_at: string;
};

export type UserSettings = {
  regions: string[];
  pushEnabled: boolean;
  pushToken?: string;
  pushTokenUpdatedAt?: string;
  quietHoursEnabled: boolean;
  updatedAt?: string;
};

export type PostsIndex = {
  generated_at: string;
  total: number;
  cards: NoticeCard[];
};
