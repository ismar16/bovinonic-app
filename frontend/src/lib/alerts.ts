import { browser } from '$app/environment';

import { db, type Animal, type ReproductiveEvent } from './db';

export interface AlertRow {
	animal: Animal;
	date: string;
	daysLeft: number;
	detail?: string;
}

export interface ReproAlerts {
	calvingSoon: AlertRow[];
	dryingOffSoon: AlertRow[];
	daysOpen: AlertRow[];
}

const CALVING_WINDOW_DAYS = 30;
const DRYING_OFF_WINDOW_DAYS = 7;
const DAYS_OPEN_THRESHOLD = 90;

function daysBetween(from: string, to: string): number {
	return Math.round(
		(new Date(`${to}T00:00:00`).getTime() - new Date(`${from}T00:00:00`).getTime()) /
			86_400_000
	);
}

export async function computeReproAlerts(farmId: string): Promise<ReproAlerts> {
	const today = new Date().toISOString().slice(0, 10);
	const animals = (await db.animals.where('farm').equals(farmId).toArray()).filter(
		(a) => a.status === 'active'
	);
	const animalMap = new Map(animals.map((a) => [a.id, a]));
	const events = await db.reproductive_events.toArray();

	const eventsByAnimal = new Map<string, ReproductiveEvent[]>();
	for (const e of events) {
		if (!animalMap.has(e.animal)) continue;
		const list = eventsByAnimal.get(e.animal) ?? [];
		list.push(e);
		eventsByAnimal.set(e.animal, list);
	}

	const calvingSoon: AlertRow[] = [];
	const dryingOffSoon: AlertRow[] = [];
	const daysOpen: AlertRow[] = [];

	for (const [animalId, list] of eventsByAnimal) {
		list.sort((a, b) => (a.date < b.date ? -1 : 1));
		const animal = animalMap.get(animalId);
		if (!animal) continue;

		const lastService = [...list]
			.reverse()
			.find((e) => e.estimated_calving_date);
		if (lastService?.estimated_calving_date) {
			const days = daysBetween(today, lastService.estimated_calving_date);
			if (days >= 0 && days <= CALVING_WINDOW_DAYS) {
				calvingSoon.push({
					animal,
					date: lastService.estimated_calving_date,
					daysLeft: days
				});
			}
		}
		if (lastService?.suggested_drying_off_date) {
			const days = daysBetween(today, lastService.suggested_drying_off_date);
			if (days >= 0 && days <= DRYING_OFF_WINDOW_DAYS) {
				dryingOffSoon.push({
					animal,
					date: lastService.suggested_drying_off_date,
					daysLeft: days
				});
			}
		}
	}

	const eligible = animals.filter(
		(a) =>
			a.sex === 'H' &&
			(a.category === 'cow_lactating' || a.category === 'cow_dry')
	);
	for (const animal of eligible) {
		const list = (eventsByAnimal.get(animal.id) ?? []).sort((a, b) =>
			a.date < b.date ? -1 : 1
		);
		const lastCalving = [...list].reverse().find((e) => e.type === 'calving');
		if (!lastCalving) continue;
		const pregnantAfter = list.some(
			(e) =>
				e.date > lastCalving.date &&
				e.type === 'palpation' &&
				e.palpation_result === 'pregnant'
		);
		if (pregnantAfter) continue;
		const open = daysBetween(lastCalving.date, today);
		if (open > DAYS_OPEN_THRESHOLD) {
			daysOpen.push({
				animal,
				date: lastCalving.date,
				daysLeft: open,
				detail: `Último parto: ${lastCalving.date}`
			});
		}
	}

	calvingSoon.sort((a, b) => a.daysLeft - b.daysLeft);
	dryingOffSoon.sort((a, b) => a.daysLeft - b.daysLeft);
	daysOpen.sort((a, b) => b.daysLeft - a.daysLeft);

	return { calvingSoon, dryingOffSoon, daysOpen };
}

export async function computeWithdrawalCount(farmId: string): Promise<number> {
	if (!browser) return 0;
	const today = new Date().toISOString().slice(0, 10);
	const animals = await db.animals.where('farm').equals(farmId).toArray();
	const animalIds = new Set(animals.map((a) => a.id));
	const events = await db.health_events.toArray();
	const active = new Set<string>();
	for (const e of events) {
		if (!animalIds.has(e.animal)) continue;
		const end =
			e.withdrawal_end_date ??
			(() => {
				const d = new Date(`${e.date}T00:00:00`);
				d.setDate(d.getDate() + (e.withdrawal_days ?? 0));
				return d.toISOString().slice(0, 10);
			})();
		if (end >= today) active.add(e.animal);
	}
	return active.size;
}
