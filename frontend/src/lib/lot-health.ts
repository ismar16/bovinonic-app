import type { Animal, HealthEvent } from './db';
import { addDateDays } from './dates';
import { validDate } from './forms';

export interface LotHealthInput {
	farm: string; lot: string; date: string; type: HealthEvent['type']; product: string; withdrawal: string;
	selected: string[]; doses: Record<string, string>; eventIds: Record<string, string>;
}

export function buildLotHealthEvents(input: LotHealthInput, animals: Animal[], today: string): HealthEvent[] {
	if (!input.farm || !input.lot) throw new Error('Elegí una finca y un lote.');
	if (!validDate(input.date) || input.date > today) throw new Error('Elegí una fecha válida que no sea futura.');
	if (!['vaccine', 'deworming', 'antibiotic', 'vitamin'].includes(input.type)) throw new Error('Elegí un tipo de atención válido.');
	const product = input.product.trim();
	if (!product || product.length > 150) throw new Error('Indicá el producto aplicado (hasta 150 caracteres).');
	if (!/^\d+$/.test(input.withdrawal) || Number(input.withdrawal) > 3650) throw new Error('Los días de retiro deben ser un entero entre 0 y 3650.');
	if (!input.selected.length || input.selected.length > 500 || new Set(input.selected).size !== input.selected.length) throw new Error('Seleccioná entre 1 y 500 animales distintos.');
	const ids = new Set<string>();
	return input.selected.map((animalId) => {
		const animal = animals.find((row) => row.id === animalId);
		if (!animal || animal.farm !== input.farm || animal.lot !== input.lot || animal.status !== 'active') throw new Error('La selección cambió: revisá los animales activos del lote.');
		if (animal.birth_date && input.date < animal.birth_date) throw new Error(`${animal.tag}: el evento no puede ser anterior a su nacimiento.`);
		const dose = (input.doses[animalId] ?? '').trim();
		if (!dose || dose.length > 100) throw new Error(`${animal.tag}: completá la dosis con su unidad (hasta 100 caracteres).`);
		const id = input.eventIds[animalId];
		if (!id || ids.has(id)) throw new Error('No se pudieron identificar los registros. Volvé a abrir el formulario.');
		ids.add(id);
		return { id, animal: animal.id, date: input.date, type: input.type, product, dose,
			withdrawal_days: Number(input.withdrawal), withdrawal_end_date: Number(input.withdrawal) ? addDateDays(input.date, Number(input.withdrawal)) : null };
	});
}

export function existingLotHealthAnimals(events: HealthEvent[], selected: string[], date: string, type: string, product: string, ownIds: string[] = []): string[] {
	const normalized = product.trim().toLocaleLowerCase('es');
	if (!normalized) return [];
	const selectedIds = new Set(selected), exclude = new Set(ownIds);
	return [...new Set(events.filter((event) => selectedIds.has(event.animal) && !exclude.has(event.id) && event.date === date && event.type === type && event.product.trim().toLocaleLowerCase('es') === normalized).map((event) => event.animal))];
}
