# Vehicle maintenance history

Branch: feat/vehicle-maintenance-history. No deployment or production migration executed.

## Behavior

Vehicle details include a paginated maintenance history (20 items), ordered by occurrence date and ID descending, with date/type/status filters and a link to the existing occurrence editor. Filters use Sao Paulo calendar days. Metrics cover all explicitly classified occurrences for the vehicle, independent of filters. Pending means ABERTA or EM_ANALISE. Recorded costs include zero and cancelled records; missing costs contribute nothing. Last completion uses the timestamp recorded when the status changes to RESOLVIDA; reopening clears that timestamp.

Maintenance is optional metadata on the original occurrence, never a separate record. PREVENTIVA, CORRETIVA and EMERGENCIAL are explicit classifications, independent of the existing occurrence problem type. Legacy records are preserved without automatic classification or inferred vehicle links. An administrator can classify existing occurrences in the existing editor. Completion dates for previously resolved records are not inferred.

The existing driver creation flow sets the vehicle ID from the selected vehicle or current trip. Existing vehicle, trip ownership, authentication and administrator permission checks remain in force. Vehicle history is restricted to ADMIN and MASTER. Changes use the existing transactional occurrences realtime topic and frontend subscription hook.

## Files changed for this feature

- backend/app/models/entities.py: optional occurrence metadata.
- backend/app/schemas/domain.py: validation and serialization.
- backend/app/api/helpers.py: expose metadata.
- backend/app/api/occurrences.py: creation, editing and completion timestamp.
- backend/app/api/vehicles.py: paginated history, SQL aggregate metrics and filters.
- backend/migrations/versions/20261110_0022_vehicle_maintenance.py: additive nullable columns and index, no data backfill.
- backend/tests/test_vehicle_maintenance.py: linkage, isolation, updates, realtime invalidation, filters, metrics, pagination, permissions, validation and migration preservation.
- frontend/src/types/index.ts: maintenance metadata types.
- frontend/src/components/MaintenanceFields.tsx: shared creation/edit fields.
- frontend/src/components/VehicleMaintenance.tsx: history and metrics.
- frontend/src/pages/admin/EntityDetailPage.tsx: vehicle section.
- frontend/src/pages/admin/OccurrencesPage.tsx: classification editor and direct occurrence link support.
- frontend/src/pages/driver/OccurrencePage.tsx: optional maintenance metadata during creation.
- frontend/src/styles.css: responsive chronological list.

Pre-existing changes in enums.py, test_occurrence_categories.py, DashboardPage.tsx and format.ts were not authored by this feature. Pre-existing changes in occurrences.py and types/index.ts were retained.

## Validation

Backend: 32 tests passed across test_vehicle_maintenance.py, test_standalone_occurrence_migration.py, test_realtime.py, test_standalone_occurrences.py, test_occurrence_categories.py and test_vehicles.py. Run these sequentially in one pytest invocation because conftest uses a shared local SQLite test database. Use --basetemp .pytest-tmp-maintenance-final on this Windows environment.

Frontend: npm test (8 passed); npm run build passed. Existing build warning: JS bundle over 500 kB. No browser-based visual or end-to-end validation performed.

Migration was exercised only on disposable test databases, including upgrade/downgrade and preservation of original occurrence columns and vehicle ID. Before running the application against an existing database, apply the migration through the normal release process. No production data was accessed or changed.
