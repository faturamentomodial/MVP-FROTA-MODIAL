"""Map visibility is independent of permission to use a point automatically."""


def location_for_map(result):
    if result.get('schema_version') == 2:
        if result.get('selected'):
            return result['selected']
        if result.get('map_reviewed'):
            return result.get('map_point')
        return None
    candidates = result.get('candidates', [])
    return candidates[0] if candidates else None
