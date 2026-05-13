interface AssistantIconProps {
  icon: string;
  alt?: string;
  className?: string;
  imageClassName?: string;
  textClassName?: string;
}

function isImageIcon(icon: string) {
  return icon.startsWith('/') || icon.startsWith('http://') || icon.startsWith('https://') || icon.endsWith('.svg') || icon.endsWith('.png') || icon.endsWith('.webp');
}

export default function AssistantIcon({
  icon,
  alt = '助手图标',
  className = '',
  imageClassName = '',
  textClassName = 'text-xl',
}: AssistantIconProps) {
  return (
    <div className={className}>
      {isImageIcon(icon) ? (
        <img src={icon} alt={alt} className={imageClassName} />
      ) : (
        <span className={textClassName}>{icon || '✨'}</span>
      )}
    </div>
  );
}
