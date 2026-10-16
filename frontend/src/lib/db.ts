import Dexie, { type EntityTable } from 'dexie';

export interface Farm {
	id: string;
	name: string;
	location: string;
	updated_at: string;
}

export interface Owner {
	id: string;
	farm: string;
	name: string;
	id_number: string;
	phone: string;
	updated_at: string;
}

export interface Brand {
	id: string;
	farm: string;
	title_owner: string | null;
	code: string;
	updated_at: string;
}

export interface Paddock {
	id: string;
	farm: string;
	name: string;
	updated_at: string;
}

export interface Animal {
	id: string;
	farm: string;
	tag: string;
	name: string;
	sex: 'M' | 'H';
	category: string;
	birth_date: string | null;
	mother: string | null;
	father: string | null;
	paddock: string | null;
	lot?: string | null;
	owner: string | null;
	brand: string | null;
	status: 'active' | 'sold' | 'dead' | 'culled';
	status_changed_at?: string | null;
	status_reason?: string;
	photo_url?: string;
	updated_at: string;
}

export interface Weighing {
	id: string;
	animal: string;
	date: string;
	weight_kg: string;
	updated_at?: string;
}

export interface DailyMilkProduction {
	id: string; farm: string; date: string; liters: string; notes: string; updated_at?: string;
}

export interface Milking {
	id: string;
	animal: string;
	date: string;
	shift: 'AM' | 'PM';
	liters: string;
	updated_at?: string;
}

export interface ReproductiveEvent {
	id: string;
	animal: string;
	date: string;
	type: 'heat' | 'service' | 'palpation' | 'calving' | 'drying_off' | 'abortion';
	service_method?: 'natural' | 'ai' | null;
	bull_straw?: string;
	palpation_result?: 'pregnant' | 'empty' | null;
	estimated_calving_date?: string | null;
	suggested_drying_off_date?: string | null;
	updated_at?: string;
}

export interface HealthEvent {
	id: string;
	animal: string;
	date: string;
	type: 'vaccine' | 'deworming' | 'antibiotic' | 'vitamin';
	product: string;
	dose?: string;
	withdrawal_days: number;
	withdrawal_end_date?: string | null;
	updated_at?: string;
}

export interface OutboxRecord {
	id?: number;
	collection:
		| 'animals'
		| 'owners'
		| 'brands'
		| 'paddocks'
		| 'lots'
		| 'agreements'
		| 'sales'
		| 'sale_payments'
		| 'sale_expenses'
		| 'weighings'
		| 'milkings'
		| 'daily_milk'
		| 'reproductive_events'
		| 'health_events';
	record_id: string;
	payload: Record<string, unknown>;
	created_at: string;
}

export interface SyncMeta {
	key: string;
	value: string;
}

export interface AnimalLot {
	id: string;
	farm: string;
	name: string;
	description: string;
	updated_at?: string;
}

export interface AgreementAnimal {
	animal: string; tag: string; name: string;
	initial_weight: string | null; final_weight: string | null;
	price_per_kg: string | null; final_date: string | null;
}
export interface AgreementExpense {
	id: string; date: string; concept: string; amount: string;
	paid_by: 'owner' | 'partner'; animal: string | null;
}
export interface AgreementSettlement {
	kind: string; expenses: string; owner_paid: string; partner_paid: string;
	partner_reimbursement?: string;
	lines?: { animal: string; gain_kg: string; sale_value: string; initial_value: string; gain_value: string; assigned_expenses: string }[];
	sale_value?: string; initial_value?: string; gain_value?: string; net_gain?: string;
	owner_part?: string; partner_part?: string; owner_total?: string; partner_total?: string;
}
export interface AnimalAgreement {
	id: string; farm: string; title: string; owner_name: string; partner_name: string; external_farm: string;
	kind: 'weight_gain' | 'sale' | 'offspring' | 'pasture'; currency: 'NIO' | 'USD'; owner_share: string;
	start_date: string; end_date: string | null; status: 'active' | 'settled'; notes: string;
	animals: AgreementAnimal[]; expenses: AgreementExpense[]; settlement?: AgreementSettlement | null;
	accept_loss?: boolean; updated_at?: string;
	sale_receipts?: { sale: string; date: string; animals: string[] }[];
}

export interface SaleLine {
	animal: string; tag: string; name?: string; weight_kg: string; price_per_kg: string;
	agreement: string | null; agreement_version: string | null;
	expenses: { concept: string; amount: string; paid_by: 'owner' | 'partner' }[];
	value?: string; settlement?: AgreementSettlement | null;
	allocated_expenses?: AgreementExpense[]; agreement_title?: string; partner_name?: string;
	subsequent_expenses?: SaleExpense[]; original_settlement?: AgreementSettlement | null;
	expenses_total?: string; net_after_expenses?: string;
	owner_name?: string; kind?: string | null; initial_weight?: string | null; owner_share?: string;
}
export interface AnimalSale {
	id: string; farm: string; date: string; buyer: string; buyer_phone: string; currency: 'NIO' | 'USD';
	notes: string; lines: SaleLine[]; total?: string; updated_at?: string; accept_loss?: boolean;
}
export interface SaleExpense {
 id: string; farm: string; sale: string; animal: string; date: string; concept: string; amount: string;
 paid_by: 'owner' | 'partner'; created_at?: string; updated_at?: string; accept_loss?: boolean;
}
export interface SalePayment {
	id: string; farm: string; sale: string; date: string; amount: string;
	method: 'cash' | 'transfer' | 'other'; reference: string; updated_at?: string;
}

class GanaderiaDB extends Dexie {
	sale_expenses!: EntityTable<SaleExpense, 'id'>;
	sales!: EntityTable<AnimalSale, 'id'>;
	sale_payments!: EntityTable<SalePayment, 'id'>;
	agreements!: EntityTable<AnimalAgreement, 'id'>;
	lots!: EntityTable<AnimalLot, 'id'>;
	farms!: EntityTable<Farm, 'id'>;
	owners!: EntityTable<Owner, 'id'>;
	brands!: EntityTable<Brand, 'id'>;
	paddocks!: EntityTable<Paddock, 'id'>;
	animals!: EntityTable<Animal, 'id'>;
	weighings!: EntityTable<Weighing, 'id'>;
	daily_milk!: EntityTable<DailyMilkProduction, 'id'>;
	milkings!: EntityTable<Milking, 'id'>;
	reproductive_events!: EntityTable<ReproductiveEvent, 'id'>;
	health_events!: EntityTable<HealthEvent, 'id'>;
	outbox!: EntityTable<OutboxRecord, 'id'>;
	sync_meta!: EntityTable<SyncMeta, 'key'>;

	constructor() {
		super('ganaderia');
		this.version(1).stores({
			farms: 'id, name, updated_at',
			owners: 'id, farm, name, updated_at',
			brands: 'id, farm, code, updated_at',
			paddocks: 'id, farm, name, updated_at',
			animals: 'id, farm, tag, status, updated_at',
			weighings: 'id, animal, date, updated_at',
			milkings: 'id, animal, date, updated_at',
			reproductive_events: 'id, animal, date, type, updated_at',
			health_events: 'id, animal, date, type, updated_at',
			outbox: '++id, collection, record_id, created_at',
			sync_meta: 'key'
		});
		this.version(2).stores({
			lots: 'id, farm, name, updated_at',
			animals: 'id, farm, tag, status, lot, updated_at'
		});
		this.version(3).stores({ agreements: 'id, farm, status, start_date, updated_at' });
		this.version(4).stores({ sales: 'id, farm, date, updated_at', sale_payments: 'id, farm, sale, date, updated_at' });
		this.version(5).stores({ sale_expenses: 'id, farm, sale, animal, date, updated_at' });
		this.version(6).stores({ daily_milk: 'id, farm, date, [farm+date], updated_at' });
	}
}

export const db = new GanaderiaDB();
