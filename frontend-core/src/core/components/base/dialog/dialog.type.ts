export interface BaseDialogProps {
  title?: string;
  persistent?: boolean;
  subTitle?: string;
  leftFull?: boolean;
}

export interface BaseDialogEmits {
  (e: "close"): void;
  (e: "confirm"): void;
}
