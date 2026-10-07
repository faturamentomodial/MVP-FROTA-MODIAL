export type Role = 'ADMIN' | 'MOTORISTA'
export type VehicleStatus = 'DISPONIVEL' | 'EM_VIAGEM' | 'ATENCAO' | 'INATIVO'
export type TripStatus = 'ABERTA' | 'EM_ANDAMENTO' | 'FINALIZADA' | 'CANCELADA'
export type OccurrenceStatus = 'ABERTA' | 'EM_ANALISE' | 'RESOLVIDA' | 'CANCELADA'
export type OccurrenceType = 'ACIDENTE' | 'AVARIA' | 'PROBLEMA_MECANICO' | 'PROBLEMA_ELETRICO' | 'PNEU' | 'PROBLEMA_ENTREGA' | 'CLIENTE_AUSENTE' | 'ATRASO' | 'MULTA' | 'ABASTECIMENTO' | 'OUTRO'

export interface User { id: number; nome: string; email: string; role: Role; ativo: boolean }
export interface AuthResponse { access_token: string; token_type: string; user: User }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number; pages: number }
export interface Driver { id: number; nome: string; cpf: string; telefone: string; email?: string; ativo: boolean; user_id: number; created_at: string; updated_at: string }
export interface Vehicle { id: number; placa: string; marca: string; modelo: string; tipo: string; km_atual: number; status: VehicleStatus; ativo: boolean; created_at: string; updated_at: string }
export type DeliveryStatus = 'PENDENTE' | 'EM_ENTREGA' | 'ENTREGUE' | 'NAO_ENTREGUE'
export interface TripInvoice { position: number; id: number; numero_nota: string; volumes: number; status: DeliveryStatus; started_at: string | null; delivered_at: string | null; occurrence_at: string | null; occurrence_reason: string | null; occurrence_note: string | null }
export interface Trip { delivery_revision: number; id: number; driver_id: number; vehicle_id: number; data_saida: string; km_inicial: number; data_retorno?: string; km_final?: number; km_percorrido?: number; status: TripStatus; observacao?: string; driver_name?: string; vehicle_plate?: string; checklist_id?: number; occurrence_count: number; notas: TripInvoice[]; total_volumes: number }
export interface ChecklistItem { id: number; nome: string; descricao?: string; ativo: boolean; ordem: number; obrigatorio: boolean }
export interface ChecklistAnswer { id: number; checklist_item_id: number; status: 'OK' | 'PROBLEMA'; observacao?: string; foto_url?: string; item: ChecklistItem }
export interface Checklist { id: number; trip_id: number; driver_id: number; vehicle_id: number; data_hora: string; status: 'APROVADO' | 'COM_PROBLEMAS'; observacao?: string; answers: ChecklistAnswer[] }
export interface Attachment { id?: number; file_url: string; file_name: string; mime_type: string }
export interface Occurrence { invoice_id?: number | null; id: number; trip_id: number; driver_id: number; vehicle_id: number; tipo: OccurrenceType; descricao: string; data_hora: string; local?: string; status: OccurrenceStatus; observacao_gestor?: string; attachments: Attachment[]; driver_name?: string; vehicle_plate?: string }
export interface Dashboard { delivery_routes: {id:number;driver_name:string;total:number;delivered:number;failed:number;pending:number;last_delivered_at:string|null}[]; total_vehicles: number; available_vehicles: number; vehicles_in_trip: number; vehicles_attention: number; inactive_vehicles: number; total_trips: number; total_checklists: number; checklists_today: number; checklists_this_week: number; checklists_this_month: number; checklists_with_problems: number; total_occurrences: number; open_occurrences: number; in_analysis_occurrences: number; resolved_occurrences: number; total_km: number; checklist_series: {date:string;total:number}[]; occurrence_by_type: {type:string;total:number}[]; drivers: {id:number;name:string;trips:number;checklists:number;occurrences:number;km:number}[]; vehicles: {id:number;plate:string;model:string;status:VehicleStatus;km:number;trips:number;occurrences:number}[] }
