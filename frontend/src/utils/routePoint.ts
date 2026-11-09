import type { Point } from '../types/routePlans'

export function routePoint(point: Point): Point
export function routePoint(point: Point | null): Point | null
export function routePoint(point: Point | null): Point | null {
  if (!point) return null
  return { address: point.address, latitude: point.latitude, longitude: point.longitude }
}
