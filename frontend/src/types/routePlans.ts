export type Point = {address:string;latitude:number;longitude:number;house_number_found?:boolean}
export type Note = {number:string;volumes:number;destination:Point;source:'MANUAL'|'SANKHYA';external_id:string|null}
export type InvoiceLookup = {number:string;external_id:string;company:string;series:string;partner:string;volumes:number|null;address:string;source:'SANKHYA'}
export type Plan = {id:number;revision:number;status:string;name:string;vehicle_id:number|null;driver_id:number|null;profile:'car'|'truck';origin:Point|null;invoices:Note[];objective:'duration'|'distance';stops:(Point & {invoices:string[]})[];result:null|{distance:number;duration:number;geometry:{coordinates:number[][]};warning:string|null;return_to_origin?:boolean}}
