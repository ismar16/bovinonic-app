import { farmDate, addDateDays } from './dates';
import { db, type Animal, type Milking, type Weighing, type DailyMilkProduction } from './db';

export interface MilkDayRow {
	date: string;
	am: number | null;
	pm: number | null;
	total: number;
	source: 'daily' | 'individual';
	hasIndividual: boolean;
}

export interface MilkCowRow {
	animal: Animal;
	total: number;
	days: number;
	avgPerDay: number;
}

export interface GmdAlertRow {
	animal: Animal;
	lastDate: string;
	prevWeight: number;
	lastWeight: number;
	gmd: number;
	days: number;
}

export function daysAgo(n: number): string {
	return addDateDays(farmDate(), -n);
}

export async function milkTodayTotal(farmId: string): Promise<number> {
	const today = daysAgo(0);
	const rows = await milkByDay(farmId, today, today);
	return rows.length > 0 ? rows[0].total : 0;
}

export async function milkByDay(
	farmId: string,
	from: string,
	to: string
): Promise<MilkDayRow[]> {
	const animals = await db.animals.where('farm').equals(farmId).toArray();
	const ids = new Set(animals.map((a) => a.id));
	const milkings = (await db.milkings.toArray()).filter(
		(m) => ids.has(m.animal) && m.date >= from && m.date <= to
	);
	const daily = (await db.daily_milk.where('farm').equals(farmId).toArray()).filter((r) => r.date >= from && r.date <= to);
	const pending = new Set((await db.outbox.toArray()).filter((r) => r.collection === 'daily_milk').map((r) => r.record_id));
	return milkDayTotals(milkings, daily, pending);
}

/** A declared farm total replaces the individual sum for its day, including zero. */
export function milkDayTotals(milkings: Milking[], daily: DailyMilkProduction[], pending = new Set<string>()): MilkDayRow[] {
	const byDay = new Map<string, MilkDayRow>();
	for (const m of milkings) {
		const row = byDay.get(m.date) ?? { date: m.date, am: 0, pm: 0, total: 0, source:'individual', hasIndividual:true };
		const cents = Math.round(Number(m.liters) * 100);
		if (m.shift === 'AM') row.am = (Math.round((row.am ?? 0)*100) + cents)/100;
		else row.pm = (Math.round((row.pm ?? 0)*100) + cents)/100;
		row.total = (Math.round(row.total*100) + cents)/100;
		byDay.set(m.date, row);
	}
	for (const record of [...daily].sort((a,b) => Number(pending.has(a.id))-Number(pending.has(b.id)) || (a.updated_at ?? '').localeCompare(b.updated_at ?? '') || a.id.localeCompare(b.id))) {
		byDay.set(record.date,{date:record.date,am:null,pm:null,total:Number(record.liters),source:'daily',hasIndividual:byDay.get(record.date)?.hasIndividual ?? false});
	}
	return [...byDay.values()].sort((a, b) => (a.date < b.date ? 1 : -1));
}

export async function exportMilkTotalsCsv(farmId: string, from = '0001-01-01', to = farmDate()): Promise<void> {
	const rows = await milkByDay(farmId,from,to);
	downloadCsv('produccion-diaria.csv',toCsv(['fecha','origen','manana_litros','tarde_litros','total_litros'],rows.map((r) => [r.date,r.source === 'daily' ? 'Total diario de finca' : 'Registros individuales',r.am,r.pm,r.total])));
}

export async function milkByCow(
	farmId: string,
	from: string,
	to: string
): Promise<MilkCowRow[]> {
	const animals = await db.animals.where('farm').equals(farmId).toArray();
	const animalMap = new Map(animals.map((a) => [a.id, a]));
	const milkings = (await db.milkings.toArray()).filter(
		(m) => animalMap.has(m.animal) && m.date >= from && m.date <= to
	);
	const byCow = new Map<string, { total: number; days: Set<string> }>();
	for (const m of milkings) {
		const row = byCow.get(m.animal) ?? { total: 0, days: new Set<string>() };
		row.total += parseFloat(m.liters) || 0;
		row.days.add(m.date);
		byCow.set(m.animal, row);
	}
	return [...byCow.entries()]
		.map(([animalId, row]) => ({
			animal: animalMap.get(animalId) as Animal,
			total: Math.round(row.total * 100) / 100,
			days: row.days.size,
			avgPerDay: row.days.size > 0 ? Math.round((row.total / row.days.size) * 100) / 100 : 0
		}))
		.sort((a, b) => b.total - a.total);
}

export async function gmdAlerts(farmId: string): Promise<GmdAlertRow[]> {
	const animals = (await db.animals.where('farm').equals(farmId).toArray()).filter(
		(a) => a.status === 'active'
	);
	const weighings = await db.weighings.toArray();
	const byAnimal = new Map<string, Weighing[]>();
	for (const w of weighings) {
		const list = byAnimal.get(w.animal) ?? [];
		list.push(w);
		byAnimal.set(w.animal, list);
	}
	const rows: GmdAlertRow[] = [];
	for (const animal of animals) {
		const list = (byAnimal.get(animal.id) ?? []).sort((a, b) =>
			a.date.localeCompare(b.date) || (a.updated_at ?? '').localeCompare(b.updated_at ?? '')
		);
		if (list.length < 2) continue;
		const last = list[list.length - 1];
		const prev = [...list].reverse().find((row) => row.date < last.date);
		if (!prev) continue;
		const days = Math.round((Date.parse(last.date) - Date.parse(prev.date)) / 86_400_000);
		const gmd = (parseFloat(last.weight_kg) - parseFloat(prev.weight_kg)) / days;
		if (gmd <= 0.1) {
			rows.push({
				animal,
				lastDate: last.date,
				prevWeight: parseFloat(prev.weight_kg),
				lastWeight: parseFloat(last.weight_kg),
				gmd: Math.round(gmd * 100) / 100,
				days
			});
		}
	}
	return rows.sort((a, b) => a.gmd - b.gmd);
}

export function toCsv(headers: string[], rows: (string | number | null)[][]): string {
	const escape = (value: string | number | null) => {
		if (value === null || value === undefined) return '';
		const raw = String(value);
		const s = typeof value === 'string' && /^[=+@\-\t\r]/.test(raw) ? `'${raw}` : raw;
		return s.includes(',') || s.includes('"') || s.includes('\n')
			? `"${s.replace(/"/g, '""')}"`
			: s;
	};
	return [headers, ...rows].map((row) => row.map(escape).join(',')).join('\n');
}

export function downloadCsv(filename: string, csv: string): void {
	const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}

export async function exportAnimalsCsv(farmId: string): Promise<void> {
	const animals = await db.animals.where('farm').equals(farmId).toArray();
	const byId = new Map(animals.map((a) => [a.id, a]));
	const [lots, paddocks, owners, brands] = await Promise.all([db.lots.where('farm').equals(farmId).toArray(), db.paddocks.where('farm').equals(farmId).toArray(), db.owners.where('farm').equals(farmId).toArray(), db.brands.where('farm').equals(farmId).toArray()]);
	const csv = toCsv(
		['arete', 'nombre', 'sexo', 'categoria', 'estado', 'nacimiento', 'madre', 'padre', 'lote', 'potrero', 'propietario', 'fierro'],
		animals.map((a) => [
			a.tag,
			a.name,
			a.sex,
			a.category,
			a.status,
			a.birth_date,
			a.mother ? (byId.get(a.mother)?.tag ?? a.mother) : '',
			a.father ? (byId.get(a.father)?.tag ?? a.father) : '',
			lots.find((l) => l.id === a.lot)?.name ?? '', paddocks.find((p) => p.id === a.paddock)?.name ?? '', owners.find((o) => o.id === a.owner)?.name ?? '', brands.find((b) => b.id === a.brand)?.code ?? ''
		])
	);
	downloadCsv('animales.csv', csv);
}

export async function exportWeighingsCsv(farmId: string): Promise<void> {
	const animals = await db.animals.where('farm').equals(farmId).toArray();
	const tagById = new Map(animals.map((a) => [a.id, a.tag]));
	const weighings = (await db.weighings.toArray())
		.filter((w) => tagById.has(w.animal))
		.sort((a, b) => (a.date < b.date ? -1 : 1));
	const csv = toCsv(
		['arete', 'fecha', 'peso_kg'],
		weighings.map((w) => [tagById.get(w.animal) ?? '', w.date, w.weight_kg])
	);
	downloadCsv('pesajes.csv', csv);
}

export async function exportMilkingsCsv(farmId: string): Promise<void> {
	const animals = await db.animals.where('farm').equals(farmId).toArray();
	const tagById = new Map(animals.map((a) => [a.id, a.tag]));
	const milkings = (await db.milkings.toArray())
		.filter((m) => tagById.has(m.animal))
		.sort((a, b) => (a.date < b.date ? -1 : 1));
	const csv = toCsv(
		['arete', 'fecha', 'turno', 'litros'],
		milkings.map((m) => [tagById.get(m.animal) ?? '', m.date, m.shift, m.liters])
	);
	downloadCsv('ordenos.csv', csv);
}
