import { useUserStore } from "@/auth/store/user.store";
import { defineStore } from "pinia";
import { ref } from "vue";

type SocketStatus = "CONNECTED" | "DISCONNECTED" | "CONNECTING";

interface DataSocket {
  status: SocketStatus;
  lastMessage: string | null;
  subscribers: number;
  reconnectTimer: number;
}

const config = {
  url: "ws://65.109.200.186:8000/ws",
};

export const useSocketStore = defineStore("socket", () => {
  const sockets = ref<Record<string, DataSocket>>({});
  const user = useUserStore();

  const createSocket = (datasetId: string) => {
    if (sockets.value[datasetId]) {
      sockets.value[datasetId].subscribers++;
      return sockets.value[datasetId];
    }
    const socket = new WebSocket(
      `${config.url}/datasets/${datasetId}/?token=${user.token?.access}`
    );

    const socketObj: DataSocket = {
      status: "CONNECTING",
      lastMessage: null,
      subscribers: 1,
      reconnectTimer: 0,
    };

    socket.onopen = () => {
      socketObj.status = "CONNECTED";
      console.log(`[WS ${datasetId}] Connected`);
    };

    socket.onclose = (err) => {
      socketObj.status = "DISCONNECTED";
      console.log(`[WS ${datasetId}] Disconnected`);

      // 🔁 auto reconnect
      socketObj.reconnectTimer = window.setTimeout(() => {
        if (socketObj.subscribers > 0) {
          console.log(`[WS ${datasetId}] Reconnecting...`);
          delete sockets.value[datasetId];
          createSocket(datasetId);
        }
      }, 3000);
    };

    socket.onmessage = (event) => {
      try {
        socketObj.lastMessage = JSON.parse(event.data);
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    sockets.value[datasetId] = socketObj;
    return socketObj;
  };

  const releaseSocket = (datasetId: string) => {
    const sock = sockets.value[datasetId] as any;
    if (!sock) return;

    sock.subscribers--;

    if (sock.subscribers <= 0) {
      console.log(`[WS ${datasetId}] Closed (no subscribers)`);
      sock.close();
      clearTimeout(sock.reconnectTimer);
      delete sockets.value[datasetId];
    }
  };

  return {
    sockets,
    createSocket,
    releaseSocket,
  };
});
