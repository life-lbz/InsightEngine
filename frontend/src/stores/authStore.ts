import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserInfo } from "../types";

interface AuthState {
  // 状态
  accessToken: string | null;
  refreshToken: string | null;
  user: UserInfo | null;
  isAuthenticated: boolean;

  // 操作
  setAuth: (tokens: {
    access_token: string;
    refresh_token: string;
    user: UserInfo;
  }) => void;
  updateAccessToken: (token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      setAuth: (tokens) =>
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          user: tokens.user,
          isAuthenticated: true,
        }),

      updateAccessToken: (token) =>
        set({ accessToken: token }),

      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        }),
    }),
    {
      name: "insight-engine-auth",
      // 仅持久化 token 和用户信息，isAuthenticated 由 accessToken 是否存在派生
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
      // 恢复时根据 accessToken 是否存在重新计算 isAuthenticated
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.isAuthenticated = !!state.accessToken;
        }
      },
    }
  )
);