import type { Animal, AnimalAgreement, PasturePayment } from './db';
import { units, decimal } from './agreements';
import { validDate } from './forms';
import { addDateDays } from './dates';

export function periodEnd(month: string): string {
	if (!/^\d{4}-\d{2}$/.test(month) || !validDate(`${month}-01`)) throw new Error('Elegí un mes válido.');
	const start = new Date(`${month}-01T12:00:00Z`); start.setUTCMonth(start.getUTCMonth()+1);
	return addDateDays(start.toISOString().slice(0,10),-1);
}
export function paymentAnimals(payment: PasturePayment): string[] { return payment.animal_ids ?? payment.animals?.map((r) => r.animal) ?? []; }
export function rentTotal(payment: PasturePayment): string { return payment.total ?? decimal(units(payment.price_per_animal,1n,999999999n)*BigInt(paymentAnimals(payment).length)); }

export function eligibleRentAnimals(agreement: AnimalAgreement, animals: Animal[], period: string) {
	if (!/^\d{4}-\d{2}$/.test(period)) return [];
	return agreement.animals.filter((row) => {
		const animal = animals.find((a) => a.id === row.animal);
		const sale = agreement.sale_receipts?.find((s) => s.animals.includes(row.animal));
		const exit = sale?.date ?? (animal?.status !== 'active' ? animal?.status_changed_at : null);
		return !(exit && exit < `${period}-01`);
	});
}

export function validatePasturePayment(input: PasturePayment, agreement: AnimalAgreement, existing: PasturePayment[], today: string): PasturePayment {
	const data = structuredClone(input), end = periodEnd(data.period.slice(0,7));
	if (agreement.kind !== 'pasture' || data.agreement !== agreement.id || data.farm !== agreement.farm) throw new Error('Seleccioná un acuerdo de pasto alquilado de esta finca.');
	if (data.period !== data.period.slice(0,7)+'-01' || data.period > today.slice(0,7)+'-01' || end < agreement.start_date || (agreement.end_date && data.period > agreement.end_date)) throw new Error('El mes debe corresponder al período del acuerdo y no ser futuro.');
	if (!validDate(data.date) || data.date > today || data.date < agreement.start_date || data.date < data.period) throw new Error('La fecha del pago debe estar entre el inicio del mes/acuerdo y hoy.');
	const ids = paymentAnimals(data);
	if (!ids.length || ids.length > 500 || new Set(ids).size !== ids.length || ids.some((id) => !agreement.animals.some((a) => a.animal === id))) throw new Error('Elegí entre 1 y 500 animales distintos de este acuerdo.');
	const paid = new Set(existing.filter((p) => p.id !== data.id && p.agreement === data.agreement && p.period === data.period).flatMap(paymentAnimals));
	if (ids.some((id) => paid.has(id))) throw new Error('Hay animales con una mensualidad registrada o pendiente para este mes. Revisá el historial.');
	data.price_per_animal = decimal(units(data.price_per_animal,1n,999999999n)); data.animal_ids = ids;
	data.total = decimal(units(data.price_per_animal)*BigInt(ids.length)); units(data.total,1n);
	data.currency = agreement.currency; data.recipient = agreement.partner_name;
	data.notes = data.notes.trim(); if (data.notes.length > 500) throw new Error('Las observaciones admiten hasta 500 caracteres.');
	return data;
}
