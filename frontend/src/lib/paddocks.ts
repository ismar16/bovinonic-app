import type { Animal, Paddock, PaddockMovement } from './db';
import { validDate, decimalValue } from './forms';

export function paddockSettings(area: string, unit: string, days: string) {
	if (!['mz', 'ha', 'm2'].includes(unit)) throw new Error('Elegí una unidad de superficie.');
	const value = area.trim() ? decimalValue(area) : null;
	if (value !== null && value > 99999999.99) throw new Error('La superficie es demasiado grande.');
	if (days && (!/^\d+$/.test(days) || Number(days) < 1 || Number(days) > 3650)) throw new Error('Indicá entre 1 y 3650 días de ocupación.');
	return { area: value === null ? null : value.toFixed(2), area_unit: unit as Paddock['area_unit'], max_occupation_days: days ? Number(days) : null };
}

export function occupation(paddock: Pick<Paddock, 'id' | 'max_occupation_days'>, animals: Animal[], today: string) {
	const current = animals.filter((a) => a.status === 'active' && a.paddock === paddock.id);
	const dates = current.map((a) => a.paddock_since).filter((d): d is string => !!d && validDate(d)).sort();
	const days = dates.length ? Math.max(0, Math.floor((Date.parse(today + 'T12:00:00Z') - Date.parse(dates[0] + 'T12:00:00Z')) / 86400000)) : null;
	return { count: current.length, days, unknown: current.length - dates.length, limitReached: days !== null && !!paddock.max_occupation_days && days >= paddock.max_occupation_days };
}

export function movementRows(animals: Animal[], selected: string[], destination: string, date: string, today: string, lot: string | null): PaddockMovement['animals'] {
	if (!validDate(date) || date > today) throw new Error('Elegí una fecha válida hasta hoy.');
	if (!destination) throw new Error('Elegí el potrero de destino.');
	if (!selected.length || selected.length > 500 || new Set(selected).size !== selected.length) throw new Error('Seleccioná entre 1 y 500 animales distintos.');
	return selected.map((id) => {
		const animal = animals.find((a) => a.id === id);
		if (!animal || animal.status !== 'active' || (lot && animal.lot !== lot)) throw new Error('Revisá los animales activos y su lote.');
		if (animal.paddock === destination) throw new Error(`${animal.tag}: ya está en el destino.`);
		if ((animal.birth_date && date < animal.birth_date) || (animal.paddock_since && date < animal.paddock_since)) throw new Error(`${animal.tag}: revisá la fecha respecto a su nacimiento y último traslado.`);
		return { animal: id, from_paddock: animal.paddock ?? null, previous_movement: animal.paddock_movement ?? null };
	});
}
