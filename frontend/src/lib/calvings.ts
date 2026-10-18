import type { Animal, CalvingRecord } from './db';
import { validDate, decimalValue } from './forms';

export function validateCalving(input: CalvingRecord, mother: Animal, animals: Animal[], today: string): CalvingRecord {
	const data=structuredClone(input);
	if(data.farm!==mother.farm || data.mother!==mother.id || mother.sex!=='H') throw new Error('Elegí una madre de esta finca.');
	if(!validDate(data.date) || data.date>today || (mother.birth_date && data.date<=mother.birth_date)) throw new Error('Elegí una fecha posterior al nacimiento de la madre y no futura.');
	if(!data.mother_version || data.mother_version!==mother.updated_at) throw new Error('Volvé a seleccionar la madre para revisar su ficha actual.');
	if(!['normal','assisted','complicated'].includes(data.delivery) || !['keep','cow_lactating','cow_nursing','cow_dry'].includes(data.maternal_status)) throw new Error('Revisá el resultado del parto y la situación de la madre.');
	if(mother.status!=='active' && (data.maternal_status!=='keep' || data.location.change_mother_lot || data.location.change_mother_paddock || !mother.status_changed_at || data.date>mother.status_changed_at)) throw new Error('Para madres inactivas, conservá su situación y registrá únicamente un parto histórico anterior a su salida.');
	if(!data.calves.length || data.calves.length>5) throw new Error('Registrá entre una y cinco crías.');
	const ids=new Set<string>(),tags=new Set<string>();
	data.calves=data.calves.map((row)=>{
		if(!['new','existing','stillborn'].includes(row.mode)) throw new Error('Elegí cómo registrar cada cría.');
		const normalized={...row};
		if(row.mode==='stillborn') normalized.animal=null;
		else {
			if(!row.animal || ids.has(row.animal)) throw new Error('Cada cría viva debe aparecer una sola vez.');
			ids.add(row.animal);
		}
		if(row.mode==='existing') {
			const calf=animals.find((a)=>a.id===row.animal && a.farm===data.farm);
			if(!calf || calf.id===mother.id || calf.birth_record || (calf.mother && calf.mother!==mother.id) || (calf.birth_date && calf.birth_date!==data.date)) throw new Error('La cría existente debe tener una madre y nacimiento compatibles, sin otro parto vinculado.');
			delete normalized.tag;delete normalized.name;delete normalized.sex;
		} else {
			if(!(row.mode==='stillborn'?['H','M','unknown']:['H','M']).includes(row.sex??'')) throw new Error('Indicá el sexo de cada cría.');
			normalized.tag=row.mode==='new'?(row.tag??'').trim():'';normalized.name=(row.name??'').trim();
			if(normalized.tag.length>50 || normalized.name.length>150) throw new Error('El arete admite 50 caracteres y el nombre 150.');
			if(row.mode==='new' && normalized.tag) {
				const tag=normalized.tag.toLocaleLowerCase('es');
				if(tags.has(tag) || animals.some((a)=>a.tag.toLocaleLowerCase('es')===tag)) throw new Error('Ese arete ya está registrado. Vinculá la cría existente o usá otro arete.');
				tags.add(tag);
			}
		}
		if(row.weight_kg) { const weight=decimalValue(row.weight_kg);if(weight>99999.99) throw new Error('Revisá el peso al nacer.');normalized.weight_kg=weight.toFixed(2); }
		else normalized.weight_kg=null;
		return normalized;
	});
	if(data.location.change_mother_paddock) {
		if(!data.location.mother_paddock) throw new Error('Elegí el potrero de destino de la madre.');
		if(data.location.mother_paddock!==mother.paddock && mother.paddock_since && data.date<mother.paddock_since) throw new Error('El traslado no puede ser anterior al último ingreso de la madre a su potrero.');
	}
	data.notes=data.notes.trim();if(data.notes.length>1000) throw new Error('Las observaciones admiten hasta 1000 caracteres.');
	return data;
}

export const maternalLabels: Record<string,string>={keep:'Conservar categoría actual',cow_lactating:'Vaca en ordeño',cow_nursing:'Vaca con cría',cow_dry:'Vaca seca'};
export const deliveryLabels: Record<string,string>={normal:'Normal',assisted:'Asistido',complicated:'Con complicaciones'};
