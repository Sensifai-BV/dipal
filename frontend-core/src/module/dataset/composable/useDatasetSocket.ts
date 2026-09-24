import { useSocketStore } from "@/core/store/data-set.socket.store";
import { onUnmounted } from "vue";

export const useDatasetSocket = (datasetId: string) => {
  const socketStore = useSocketStore();
  const socket = socketStore.createSocket(datasetId);

  onUnmounted(() => {
    socketStore.releaseSocket(datasetId);
  });

  return {
    status: socket.status,
    lastMessage: socket.lastMessage,
  };
};
