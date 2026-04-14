export interface ChatUploadItem {
  id: string;
  name: string;
  size: number;
  type: string;
  content?: string;
  status?: "pending" | "uploading" | "done" | "error";
}
