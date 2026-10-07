import { CheckCircle2, LoaderCircle, X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import { labelEnum } from '../utils/format'

export function Button({ children, loading, variant = 'primary', className = '', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & {loading?:boolean;variant?:'primary'|'secondary'|'danger'|'ghost'}) {
  return <button className={`button button--${variant} ${className}`} disabled={loading || props.disabled} {...props}>
    {loading ? <LoaderCircle className="spin" size={20} aria-hidden /> : children}
  </button>
}

export function Alert({ children, tone = 'error' }: {children:ReactNode;tone?:'error'|'success'|'info'}) {
  return <div className={`alert alert--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{tone === 'success' && <CheckCircle2 size={18}/>} {children}</div>
}

export function StatusBadge({ value }: {value:string}) { return <span className={`status status--${value.toLowerCase()}`}>{labelEnum(value)}</span> }

export function Modal({ open, title, children, onClose }: {open:boolean;title:string;children:ReactNode;onClose:()=>void}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { if (open) closeRef.current?.focus() }, [open])
  if (!open) return null
  return <div className="modal-backdrop" role="presentation" onMouseDown={e => e.target === e.currentTarget && onClose()}>
    <section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <header><h2 id="modal-title">{title}</h2><button ref={closeRef} className="icon-button" onClick={onClose} aria-label="Fechar"><X /></button></header>
      {children}
    </section>
  </div>
}

export function Empty({ title, description }: {title:string;description:string}) { return <div className="empty"><div>↗</div><h3>{title}</h3><p>{description}</p></div> }

