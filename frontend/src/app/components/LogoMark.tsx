import { publicAsset } from '../lib/public-assets';

interface LogoMarkProps {
  className?: string;
  imageClassName?: string;
  alt?: string;
}

export default function LogoMark({
  className = '',
  imageClassName = '',
  alt = '安牛 logo',
}: LogoMarkProps) {
  return (
    <div className={className}>
      <img src={publicAsset('anniu-logo.png')} alt={alt} className={imageClassName} />
    </div>
  );
}
