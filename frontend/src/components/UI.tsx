import { Camera, CheckCircle2, ImagePlus, LoaderCircle, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
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

export function PhotoInput({ file, onChange }: {file?:File;onChange:(file?:File)=>void}) {
  const [preview, setPreview] = useState<string>()
  useEffect(() => {
    if (!file) { setPreview(undefined); return }
    const url = URL.createObjectURL(file); setPreview(url); return () => URL.revokeObjectURL(url)
  }, [file])
  return <div className="photo-input">
    {preview && <img src={preview} alt="Prévia da foto selecionada" />}
    <label className="button button--secondary"><Camera size={19}/>{file ? 'Trocar foto' : 'Adicionar foto'}<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={e => onChange(e.target.files?.[0])}/></label>
    {file && <button className="text-button" type="button" onClick={()=>onChange(undefined)}><ImagePlus size={16}/> Remover</button>}
  </div>
}

export function Empty({ title, description }: {title:string;description:string}) { return <div className="empty"><div>↗</div><h3>{title}</h3><p>{description}</p></div> }

