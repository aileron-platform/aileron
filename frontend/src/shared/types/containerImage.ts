/**
 */

export interface ContainerImage {
  id: string;
  name: string;
  description: string;
  icon: string;
  image: string;
  tags: string[];
  features: string[];
  recommended: boolean;
  active: boolean;
}

export interface ContainerImagesResponse {
  defaultImageId: string;
  images: ContainerImage[];
}

