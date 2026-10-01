import { db, type Animal, type Milking, type Weighing } from './db';

export interface MilkDayRow {
	date: string;
	am: number;
	pm: number;
	total: number;
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
	const d = new Date();
	d.setDate(d.getDate() - n);
	return d.toISOString().slice(0, 10);
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
	const byDay = new Map<string, MilkDayRow>();
	for (const m of milkings) {
		const row = byDay.get(m.date) ?? { date: m.date, am: 0, pm: 0, total: 0 };
		const liters = parseFloat(m.liters) || 0;
		if (m.shift === 'AM') row.am += liters;
		else row.pm += liters;
		row.total += liters;
		byDay.set(m.date, row);
	}
	return [...byDay.values()].sort((a, b) => (a.date < b.date ? 1 : -1));
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
			a.date < b.date ? -1 : 1
		);
		if (list.length < 2) continue;
		const last = list[list.length - 1];
		const prev = list[list.length - 2];
		const days = Math.max(
			1,
			Math.round(
				(new Date(last.date).getTime() - new Date(prev.date).getTime()) / 86_400_000
			)
		);
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

function toCsv(headers: string[], rows: (string | number | null)[][]): string {
	const escape = (value: string | number | null) => {
		if (value === null || value === undefined) return '';
		const s = String(value);
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
	const csv = toCsv(
		['arete', 'nombre', 'sexo', 'categoria', 'estado', 'nacimiento', 'madre', 'padre'],
		animals.map((a) => [
			a.tag,
			a.name,
			a.sex,
			a.category,
			a.status,
			a.birth_date,
			a.mother ? (byId.get(a.mother)?.tag ?? a.mother) : '',
			a.father ? (byId.get(a.father)?.tag ?? a.father) : ''
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
