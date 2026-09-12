export interface TokenResponse {
  access_token: string;
  username: string;
}

export interface CurrentUser {
  username: string;
  [key: string]: unknown;
}

export interface ApiError {
  detail: string;
}
