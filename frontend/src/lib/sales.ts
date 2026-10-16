import type { AnimalAgreement, AnimalSale, SaleLine } from './db';
import { agreementSettlement, decimal, rounded, units } from './agreements';
import { validDate } from './forms';
import { farmDate } from './dates';

export const paymentMethods = { cash: 'Efectivo', transfer: 'Transferencia', other: 'Otro' };

export function allocatedExpenses(agreement: AnimalAgreement, animal: string) {
	const index = agreement.animals.findIndex((r) => r.animal === animal);
	if (index < 0) throw new Error('El animal no pertenece al acuerdo.');
	const count = BigInt(agreement.animals.length);
	return agreement.expenses.filter((e) => !e.animal || e.animal === animal).map((e) => {
		const cents = units(e.amount, 1n);
		const share = e.animal ? cents : cents / count + (BigInt(index) < cents % count ? 1n : 0n);
		return { ...e, animal, amount: decimal(share) };
	}).filter((e) => e.amount !== '0.00');
}

export function saleLinePreview(line: SaleLine, agreement?: AnimalAgreement) {
	const value = decimal(rounded(units(line.weight_kg, 1n, 9999999n) * units(line.price_per_kg, 1n, 999999999n), 100n));
	if (value === '0.00') throw new Error('El importe debe ser al menos 0.01.');
	if (!agreement) return { value, settlement: null, allocated_expenses: [] };
	const original = agreement.animals.find((a) => a.animal === line.animal);
	if (!original) throw new Error('El animal no está en este acuerdo.');
	const allocated = allocatedExpenses(agreement, line.animal);
	return { value, allocated_expenses: allocated, settlement: agreementSettlement({ ...agreement,
		animals: [{ ...original, final_weight: line.weight_kg, price_per_kg: line.price_per_kg }],
		expenses: [...allocated, ...line.expenses.map((e, i) => ({ ...e, id: `extra-${i}`, date: '', animal: line.animal }))]
	}) };
}

export function validateSale(input: AnimalSale, agreements: AnimalAgreement[]): AnimalSale {
	const sale = structuredClone(input);
	sale.buyer = sale.buyer.trim(); sale.buyer_phone = sale.buyer_phone.trim(); sale.notes = sale.notes.trim();
	if (!sale.buyer || sale.buyer.length > 150 || sale.buyer_phone.length > 30 || sale.notes.length > 2000) throw new Error('Revisá el nombre, teléfono y observaciones del comprador.');
	if (!validDate(sale.date) || sale.date > farmDate()) throw new Error('Elegí una fecha de venta válida, no futura.');
	if (!['NIO', 'USD'].includes(sale.currency)) throw new Error('Elegí la moneda.');
	if (!sale.lines.length || sale.lines.length > 200 || new Set(sale.lines.map((r) => r.animal)).size !== sale.lines.length) throw new Error('Seleccioná entre 1 y 200 animales, sin repetir.');
	let total = 0n;
	for (const line of sale.lines) {
		line.weight_kg = decimal(units(line.weight_kg, 1n, 9999999n)); line.price_per_kg = decimal(units(line.price_per_kg, 1n, 999999999n));
		const agreement = agreements.find((a) => a.status === 'active' && a.animals.some((r) => r.animal === line.animal));
		if (agreement && (agreement.currency !== sale.currency || sale.date < agreement.start_date)) throw new Error(`${line.tag}: revisá moneda y fecha del acuerdo.`);
		line.agreement = agreement?.id ?? null; line.agreement_version = agreement?.updated_at ?? null;
		if (agreement && !line.agreement_version) throw new Error('Sincronizá el acuerdo antes de vender.');
		if (line.expenses.length > 200) throw new Error('Máximo 200 gastos adicionales por animal.');
		for (const e of line.expenses) {
			e.concept = e.concept.trim(); e.amount = decimal(units(e.amount, 1n));
			if (!e.concept || e.concept.length > 200 || !['owner','partner'].includes(e.paid_by) || (!agreement && e.paid_by !== 'owner')) throw new Error('Revisá concepto y pagador de los gastos.');
		}
		const preview = saleLinePreview(line, agreement);
		if (Number(preview.settlement?.net_gain ?? 0) < 0 && sale.accept_loss !== true) throw new Error('Confirmá el reparto de las pérdidas antes de registrar la venta.');
		Object.assign(line, preview); total += units(preview.value);
	}
	sale.total = decimal(total);
	units(sale.total, 1n);
	return sale;
}
