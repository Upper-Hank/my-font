export default function GlyphFrame({ src, alt, className = '', imageClassName, ...props }) {
  return <div className={`glyph-frame em-frame ${className}`}>
    <div className="em-guides" aria-hidden="true"><span className="em-center-x" /><span className="em-center-y" /><span className="em-baseline" /></div>
    <img className={imageClassName} src={src} alt={alt} {...props} />
  </div>;
}
