import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from "axios";
import { useAuthStore } from "@/stores/auth";

/**
 * Day 24 双 spec 模式（ADR-008/013）：
 * - pythonClient → Python 主壳（Memory / Soul / Identity / health），spec = docs/api/v1.yaml
 * - javaClient   → Java 业务后端（User / Session / Plugin / Connector / Permission），spec = docs/api/java-v1.yaml
 *
 * 共享：401 拦截、token 注入、错误归一。区别仅在 baseURL。
 */

const PYTHON_BASE_URL =
  import.meta.env.VITE_PYTHON_API_BASE_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "";

const JAVA_BASE_URL =
  import.meta.env.VITE_JAVA_API_BASE_URL || "";

interface ClientFlavor {
  name: "python" | "java";
}

function attachInterceptors(instance: AxiosInstance, flavor: ClientFlavor): AxiosInstance {
  instance.interceptors.request.use((config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        if (status === 401) {
          useAuthStore.getState().clearAuth();
          window.location.href = "/login";
          return Promise.reject(error);
        }
        const message =
          error.response?.data?.message || error.message || "An unexpected error occurred";
        // eslint-disable-next-line no-console
        console.error(`[API Error · ${flavor.name}] ${status}: ${message}`);
      }
      return Promise.reject(error);
    },
  );
  return instance;
}

const pythonAxios: AxiosInstance = attachInterceptors(
  axios.create({
    baseURL: PYTHON_BASE_URL,
    timeout: 30_000,
    headers: { "Content-Type": "application/json" },
  }),
  { name: "python" },
);

const javaAxios: AxiosInstance = attachInterceptors(
  axios.create({
    baseURL: JAVA_BASE_URL,
    timeout: 30_000,
    headers: { "Content-Type": "application/json" },
  }),
  { name: "java" },
);

function makeNamespace(instance: AxiosInstance) {
  return {
    raw: instance,
    async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
      const response: AxiosResponse<T> = await instance.get(url, config);
      return response.data;
    },
    async post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
      const response: AxiosResponse<T> = await instance.post(url, data, config);
      return response.data;
    },
    async put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
      const response: AxiosResponse<T> = await instance.put(url, data, config);
      return response.data;
    },
    async del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
      const response: AxiosResponse<T> = await instance.delete(url, config);
      return response.data;
    },
  };
}

export const pythonClient = makeNamespace(pythonAxios);
export const javaClient = makeNamespace(javaAxios);

/**
 * @deprecated Day 23 untyped helpers — kept for backward compatibility while we
 * migrate call sites to `pythonClient` / `javaClient`. Default points at the
 * Python instance to preserve the prior `import.meta.env.VITE_API_BASE_URL`
 * default. Remove once all consumers switched (target: Phase 3).
 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return pythonClient.get<T>(url, config);
}
/** @deprecated see {@link get} */
export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return pythonClient.post<T>(url, data, config);
}
/** @deprecated see {@link get} */
export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return pythonClient.put<T>(url, data, config);
}
/** @deprecated see {@link get} */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return pythonClient.del<T>(url, config);
}

export default pythonAxios;
