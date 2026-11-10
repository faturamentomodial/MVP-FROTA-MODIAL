import { useEffect, useState, type DependencyList, type EffectCallback } from 'react'
import { subscribeRealtime, type Topic } from '../services/realtime'

/** Re-run only a data-loading effect. Never remount the page or its form. */
export function useRealtimeEffect(topics: Topic[], effect: EffectCallback, dependencies: DependencyList) {
  const [revision, setRevision] = useState(0)
  const key = topics.join(',')
  useEffect(() => subscribeRealtime(changed => {
    if (key.split(',').some(topic => changed.has(topic as Topic))) setRevision(value => value + 1)
  }), [key])
  useEffect(effect, [...dependencies, revision])
}
