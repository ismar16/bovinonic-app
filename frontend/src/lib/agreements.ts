import type { AnimalAgreement, AgreementSettlement } from './db';
import { validDate } from './forms';
import { farmDate } from './dates';

export const agreementKinds = {
	weight_gain: 'A medias · Ganancia de peso', sale: 'A medias · Valor de venta',
	offspring: 'A medias · Crías (valor de venta)', pasture: 'Pasto alquilado'
};

function units(value: string | null, minimum = 0n, maximum = 99999999999n): bigint {
	const normalized = (value ?? '').trim().replace(',', '.');
	if (!/^\d+(\.\d{1,2})?$/.test(normalized)) throw new Error('Completá las cantidades con hasta dos decimales.');
	const [whole, fraction = ''] = normalized.split('.');
	const result = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
	if (result < minimum || result > maximum) throw new Error('La cantidad está fuera del rango permitido.');
	return result;
}
function rounded(value: bigint, divisor: bigint): bigint {
	return value < 0n ? -rounded(-value, divisor) : (value + divisor / 2n) / divisor;
}
function decimal(value: bigint): string {
	const absolute = value < 0n ? -value : value;
	return `${value < 0n ? '-' : ''}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')}`;
}
export function moneyLabel(value: string | undefined, currency: 'NIO' | 'USD'): string {
	return new Intl.NumberFormat('es-NI', { style: 'currency', currency }).format(Number(value ?? 0));
}

export function agreementSettlement(agreement: AnimalAgreement): AgreementSettlement {
	let ownerPaid = 0n, partnerPaid = 0n;
	for (const e of agreement.expenses) {
		const cost = units(e.amount, 1n);
		if (e.paid_by === 'owner') ownerPaid += cost;
		else if (e.paid_by === 'partner') partnerPaid += cost;
		else throw new Error('Indicá quién pagó cada gasto.');
	}
	const costs = ownerPaid + partnerPaid;
	const common = { kind: agreement.kind, expenses: decimal(costs), owner_paid: decimal(ownerPaid), partner_paid: decimal(partnerPaid) };
	if (agreement.kind === 'pasture') return { ...common, partner_reimbursement: decimal(partnerPaid) };
	let sale = 0n, gain = 0n, initial = 0n;
	const lines = agreement.animals.map((animal) => {
		const finalWeight = units(animal.final_weight, 1n, 9999999n);
		const initialWeight = agreement.kind === 'weight_gain' ? units(animal.initial_weight, 1n, 9999999n) : 0n;
		const price = units(animal.price_per_kg, 1n, 999999999n);
		const saleValue = rounded(finalWeight * price, 100n);
		const gainValue = rounded((finalWeight - initialWeight) * price, 100n);
		const initialValue = saleValue - gainValue;
		const assigned = agreement.expenses.filter((e) => e.animal === animal.animal).reduce((sum, e) => sum + units(e.amount, 1n), 0n);
		sale += saleValue; gain += gainValue; initial += initialValue;
		return { animal: animal.animal, gain_kg: decimal(finalWeight - initialWeight), sale_value: decimal(saleValue),
			initial_value: decimal(initialValue), gain_value: decimal(gainValue), assigned_expenses: decimal(assigned) };
	});
	const net = gain - costs;
	const ownerPart = rounded(net * units(agreement.owner_share, 0n, 10000n), 10000n);
	const partnerPart = net - ownerPart;
	return { ...common, lines, sale_value: decimal(sale), initial_value: decimal(initial), gain_value: decimal(gain),
		net_gain: decimal(net), owner_part: decimal(ownerPart), partner_part: decimal(partnerPart),
		owner_total: decimal(initial + ownerPaid + ownerPart), partner_total: decimal(partnerPaid + partnerPart) };
}

/** Validate and canonicalize before queuing; the server independently validates and recalculates. */
export function validateAgreement(input: AnimalAgreement, settle = false): AnimalAgreement {
	const data = structuredClone(input);
	if (!settle) { data.end_date = null; delete data.accept_loss; }
	for (const field of ['title', 'owner_name', 'partner_name', 'external_farm'] as const) {
		data[field] = data[field].trim();
		if (!data[field] || data[field].length > 150) throw new Error('Completá el título, las dos personas y la finca de destino (hasta 150 caracteres).');
	}
	if (!validDate(data.start_date) || data.start_date > farmDate()) throw new Error('La fecha de inicio debe ser válida y no futura.');
	if (data.end_date && (!validDate(data.end_date) || data.end_date < data.start_date || data.end_date > farmDate())) throw new Error('Revisá la fecha de cierre.');
	if (!data.animals.length) throw new Error('Seleccioná al menos un animal.');
	if (data.animals.length > 500 || data.expenses.length > 2000) throw new Error('Un acuerdo admite hasta 500 animales y 2000 gastos. Separá el registro en varios acuerdos.');
	if (new Set(data.animals.map((a) => a.animal)).size !== data.animals.length) throw new Error('Hay animales repetidos.');
	data.owner_share = decimal(units(data.owner_share, 0n, 10000n));
	for (const row of data.animals) {
		for (const field of ['initial_weight', 'final_weight', 'price_per_kg'] as const) {
			row[field] = row[field] ? decimal(units(row[field], 1n, field === 'price_per_kg' ? 999999999n : 9999999n)) : null;
		}
		if (data.kind === 'weight_gain' && !row.initial_weight) throw new Error(`${row.tag}: indicá el peso de entrega.`);
		if (row.final_date && (!validDate(row.final_date) || row.final_date < data.start_date || row.final_date > (data.end_date || farmDate()))) throw new Error(`${row.tag}: revisá la fecha final.`);
		if (settle && data.kind !== 'pasture' && (!row.final_weight || !row.price_per_kg || !row.final_date)) throw new Error(`${row.tag}: completá peso final, precio por kg y fecha final.`);
	}
	for (const e of data.expenses) {
		e.concept = e.concept.trim(); e.amount = decimal(units(e.amount, 1n));
		if (!e.concept || e.concept.length > 200) throw new Error('Cada gasto requiere un concepto de hasta 200 caracteres.');
		if (!validDate(e.date) || e.date < data.start_date || e.date > (data.end_date || farmDate())) throw new Error('La fecha de un gasto está fuera del periodo del acuerdo.');
		if (e.animal && !data.animals.some((a) => a.animal === e.animal)) throw new Error('Quitá o reasigná los gastos del animal antes de retirarlo.');
	}
	if (settle) {
		if (!data.end_date) throw new Error('Indicá la fecha de liquidación.');
		data.settlement = agreementSettlement(data);
		if (Number(data.settlement.net_gain ?? 0) < 0 && !data.accept_loss) throw new Error('El saldo es negativo. Confirmá su reparto para liquidar.');
		data.status = 'settled';
	} else { data.status = 'active'; data.settlement = null; }
	return data;
}
