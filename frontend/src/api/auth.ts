import apiClient from "./client";
import type { LoginRequest, LoginResponse, UserInfo } from "../types";

export const authApi = {
  /** 学员登录 */
  async login(data: LoginRequest): Promise<LoginResponse> {
    const response = await apiClient.post("/auth/login", data);
    return response.data;
  },

  /** 刷新 Access Token */
  async refresh(refreshToken: string): Promise<{ access_token: string }> {
    const response = await apiClient.post("/auth/refresh", {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  /** 获取当前用户信息 */
  async me(): Promise<UserInfo> {
    const response = await apiClient.get("/auth/me");
    return response.data;
  },

  /** 登出（服务端可选使 Token 失效） */
  async logout(): Promise<void> {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // 忽略登出请求失败
    }
  },
};