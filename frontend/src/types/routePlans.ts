export type Point = {address:string;latitude:number;longitude:number;house_number_found?:boolean;manual_confirmed?:boolean;precision?:string;provider?:string}
export type Note = {number:string;volumes:number;destination:Point;source:'MANUAL'|'SANKHYA';external_id:string|null}
export type InvoiceLookup = {number:string;external_id:string;company:string;series:string;partner:string;volumes:number|null;address:string;source:'SANKHYA'}
export type Plan = {addresses?:Point[];return_point?:Point|null;id:number;revision:number;status:string;name:string;vehicle_id:number|null;driver_id:number|null;profile:'car'|'truck';origin:Point|null;invoices:Note[];objective:'duration'|'distance';stops:(Point & {invoices:string[]})[];result:null|{distance:number;duration:number;geometry:{coordinates:number[][]};warning:string|null;return_to_origin?:boolean}}

export type RouteTemplate = Plan & {description:string;notes:string;active:boolean;return_point:Point|null;weekdays:number[];addresses:Point[]}
export type RouteExecution = {id:number;revision:number;template_id:number;template_revision:number;plan_id:number;name:string;date:string;departure_time:string|null;driver_id:number;vehicle_id:number;driver_name:string;vehicle_plate:string;status:string;notes:string;trip_id:number|null;snapshot:RouteTemplate;request_key:string}
