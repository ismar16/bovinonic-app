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
	owner: string | null;
	brand: string | null;
	status: 'active' | 'sold' | 'dead' | 'culled';
	status_changed_at?: string | null;
	status_reason?: string;
	updated_at: string;
}

export interface Weighing {
	id: string;
	animal: string;
	date: string;
	weight_kg: string;
	updated_at?: string;
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
		| 'weighings'
		| 'milkings'
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

class GanaderiaDB extends Dexie {
	farms!: EntityTable<Farm, 'id'>;
	owners!: EntityTable<Owner, 'id'>;
	brands!: EntityTable<Brand, 'id'>;
	paddocks!: EntityTable<Paddock, 'id'>;
	animals!: EntityTable<Animal, 'id'>;
	weighings!: EntityTable<Weighing, 'id'>;
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
	}
}

export const db = new GanaderiaDB();
