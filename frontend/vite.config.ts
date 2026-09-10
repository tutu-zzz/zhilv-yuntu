import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import os from "node:os";

// 获取本机局域网 IPv4，作为后端代理目标。
// 不用 127.0.0.1：VS Code 的自动端口转发会抢占 127.0.0.1:<port>，
// 导致 proxy 请求被 VS Code 截走并返回 404。
// 本机 IP 变化时（换网络）重启 npm run dev 即自动适配。
function getLanIPv4(): string {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const net of interfaces[name] ?? []) {
      const isIPv4 = net.family === "IPv4" || (net.family as unknown) === 4;
      if (isIPv4 && !net.internal && !net.address.startsWith("169.254")) {
        return net.address;
      }
    }
  }
  return "127.0.0.1";
}

const backendTarget = `http://${getLanIPv4()}:8000`;

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      // 与生产环境 nginx.conf 的 /api/ 代理保持一致：
      // 前端统一请求 /api/*，转发到本机后端并去掉 /api 前缀。
      "/api": {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
