export function Brand({ compact = false }: {compact?: boolean}) {
  return <div className={`brand ${compact ? 'brand--compact' : ''}`}>
    <img src="/modial-mark.svg" alt="Modial Controle de Frota" />
  </div>
}

