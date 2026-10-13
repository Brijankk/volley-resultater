from __future__ import annotations

import ast
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from volleyball_resultater.exporter import export_json


class ExporterNewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / ".sqlite"
        self.output = Path(self.directory.name) / "json"
        self.connection = sqlite3.connect(self.db)
        self.addCleanup(self.connection.close)
        # Read the actual storage schema without initializing a repository or fetching pages.
        storage = Path(__file__).resolve().parents[1] / "src/volleyball_resultater/storage.py"
        tree = ast.parse(storage.read_text(encoding="utf-8"))
        schema = next(ast.literal_eval(node.value) for node in tree.body
                      if isinstance(node, ast.Assign) and any(
                          isinstance(target, ast.Name) and target.id == "SCHEMA" for target in node.targets))
        self.connection.executescript(schema)

    def seed_pool(self):
        self.connection.execute("INSERT INTO leagues VALUES (7, 'Volleyligaen Herrer', 'Volleyball Danmark', 'Mand', 'Senior', 2025)")
        self.connection.execute("INSERT INTO pools VALUES (42, 'Øst', '7')")

    def match(self, id=1, time="2025-10-04T00:00:00", home_sets=3, away_sets=2,
              home_points=2, away_points=1, note=None, balls=True):
        self.connection.execute(
            "INSERT INTO matches (pool_id,id,match_number,match_time,home_team,away_team,"
            "venue,court,address,home_sets,away_sets,home_points,away_points,note,home_balls1,away_balls1) "
            "VALUES (42,?,?,?,'A','B','Hal','1','Adresse',?,?,?,?,?,?,?)",
            (id, 100 + id, time, home_sets, away_sets, home_points, away_points, note,
             25 if balls else None, 20 if balls else None),
        )

    def ranking(self, team, rank, played, won, lost, sets_won, sets_lost, balls_won, balls_lost, points):
        self.connection.execute("INSERT INTO rankings VALUES (42,?,?,?,?,?,?,?,?,?,?)",
                                (rank, team, played, won, lost, sets_won, sets_lost, balls_won, balls_lost, points))

    def export(self):
        self.connection.commit()
        before = self.db.read_bytes()
        export_json(self.db, self.output)
        self.assertEqual(self.db.read_bytes(), before)
        return json.loads((self.output / "42.json").read_text(encoding="utf-8"))

    def test_frontend_contract_uses_scraped_points_and_string_ids(self):
        self.seed_pool()
        self.connection.execute("INSERT INTO leagues VALUES (8, 'Unscraped league', 'Volleyball Danmark', 'Mand', 'Senior', 2026)")
        self.match()
        self.ranking('A', 1, 1, 1, 0, 3, 2, 25, 20, 2)
        self.ranking('B', 2, 1, 0, 1, 2, 3, 20, 25, 1)
        data = self.export()
        index = json.loads((self.output / "leagues.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index['leagues']), 1)
        self.assertEqual(index['leagues'][0]['id'], '7')
        self.assertEqual(index['leagues'][0]['name'], 'Volleyligaen Herrer')
        self.assertEqual(index['leagues'][0]['season_id'], '2025')
        self.assertEqual(index['leagues'][0]['division'], 'Volleyligaen')
        self.assertEqual(data['pool']['id'], '42')
        self.assertEqual(data['pool']['name'], 'Øst')
        self.assertEqual(data['pool']['league_name'], 'Volleyligaen Herrer')
        self.assertEqual(data['pool']['league_id'], '7')
        self.assertEqual(data['matches'][0]['kamp_id'], 1)
        self.assertFalse(data['matches'][0]['starts_at_time_known'])
        self.assertEqual(data['matches'][0]['starts_at'], '2025-10-04T00:00:00')
        self.assertEqual(data['matches'][0]['result_note'], '')
        self.assertNotIn('match_time', data['matches'][0])
        self.assertNotIn('home_sets', data['matches'][0])
        self.assertNotIn('id', data['matches'][0])
        self.assertNotIn('match_id', data['matches'][0])
        self.assertEqual(data['set_results'][0]['kamp_id'], 1)
        self.assertEqual(data['cumulative_points'][-2]['kamp_id'], 1)
        self.assertEqual(data['set_results'][0]['home_points'], 25)
        self.assertEqual(data['computed_standings'][0]['points'], 2)
        self.assertEqual(data['cumulative_points'][-2]['cumulative_points'], 2)
        self.assertEqual(data['metadata']['validation']['mismatch_count'], 0)

    def test_upcoming_and_undated_matches_and_repeated_pair(self):
        self.seed_pool()
        self.match()
        self.match(id=2, time=None, home_points=3, away_points=1)
        self.match(id=3, time='2025-11-01T12:00:00', home_sets=None, away_sets=None,
                   home_points=None, away_points=None, note='nan', balls=False)
        data = self.export()
        self.assertEqual(data['result_matrix']['A']['B'], '3-2, 3-2')
        self.assertIsNone(data['result_matrix']['B']['A'])
        self.assertEqual(data['result_matrix']['A']['A'], '')
        events = [e for e in data['cumulative_points'] if e['team'] == 'A']
        self.assertEqual([e['game_number'] for e in events], [0, 1, 2])
        self.assertEqual(events[-1]['cumulative_points'], 5)
        self.assertIsNone(events[-1]['date'])
        self.assertEqual(len(data['matches']), 3)
        self.assertTrue(data['matches'][1]['starts_at_time_known'])

    def test_rank_is_not_validated_and_point_mismatches_are_reported(self):
        self.seed_pool()
        self.match()
        self.ranking('A', 2, 1, 1, 0, 3, 2, 25, 20, 3)
        self.ranking('B', 1, 1, 0, 1, 2, 3, 20, 25, 1)
        data = self.export()
        self.assertEqual(data['metadata']['validation']['affected_fields'], ['points'])
        self.assertEqual(data['metadata']['validation']['mismatch_count'], 1)
        self.assertNotIn('rank', data['metadata']['validation']['compared_fields'])

    def test_forfeit_uses_administrative_ball_scores(self):
        self.seed_pool()
        self.match(home_sets=3, away_sets=0, home_points=3, away_points=0, note='UHT', balls=False)
        data = self.export()
        self.assertEqual(data['computed_standings'][0]['balls_won'], 75)
        self.assertEqual(data['computed_standings'][0]['balls_lost'], 0)

    def test_missing_awarded_points_are_not_inferred(self):
        self.seed_pool()
        self.match(home_points=None)
        data = self.export()
        a = next(row for row in data['computed_standings'] if row['team_name'] == 'A')
        self.assertIsNone(a['points'])
        self.assertIsNone(data['cumulative_points'][-2]['cumulative_points'])

    def test_missing_points_propagate_to_later_chart_totals(self):
        self.seed_pool()
        self.match(home_points=None)
        self.match(id=2, time='2025-10-05T12:00:00', home_points=3)
        data = self.export()
        events = [event for event in data['cumulative_points'] if event['team'] == 'A']
        self.assertEqual([event['cumulative_points'] for event in events], [0, None, None])
        self.assertEqual([event['game_number'] for event in events], [0, 1, 2])

    def test_pool_with_only_upcoming_matches_has_zero_totals(self):
        self.seed_pool()
        self.match(home_sets=None, away_sets=None, home_points=None, away_points=None, balls=False)
        self.ranking('A', 1, 0, 0, 0, 0, 0, 0, 0, 0)
        self.ranking('B', 2, 0, 0, 0, 0, 0, 0, 0, 0)
        data = self.export()
        self.assertEqual(data['metadata']['validation']['mismatch_count'], 0)
        self.assertEqual(len(data['cumulative_points']), 2)
        self.assertEqual(data['set_results'], [])
        self.assertIsNone(data['result_matrix']['A']['B'])

    def test_empty_pool_and_empty_database(self):
        self.connection.commit()
        export_json(self.db, self.output)
        self.assertEqual(json.loads((self.output / 'leagues.json').read_text())['pools'], [])
        self.seed_pool()
        data = self.export()
        self.assertEqual(data['matches'], [])
        self.assertEqual(data['cumulative_points'], [])
        self.assertEqual(data['result_matrix'], {})

    def test_missing_database_is_not_created(self):
        missing = Path(self.directory.name) / 'missing.sqlite'
        with self.assertRaises(sqlite3.OperationalError):
            export_json(missing, self.output)
        self.assertFalse(missing.exists())

    def test_prefixed_identifiers_keep_multiple_leagues_and_pools_separate(self):
        self.seed_pool()
        self.match()
        self.connection.execute("INSERT INTO leagues VALUES (9, '1. Division Kvinder', 'Volleyball Danmark', 'Kvinde', 'Senior', 2025)")
        self.connection.execute("INSERT INTO pools VALUES (99, 'Vest', 9)")
        self.match(id=2)
        self.connection.execute("UPDATE matches SET pool_id=99,home_team='C',away_team='D' WHERE id=2")
        data = self.export()
        other = json.loads((self.output / '99.json').read_text(encoding='utf-8'))
        self.assertEqual(data['pool']['league_id'], '7')
        self.assertEqual(other['pool']['league_id'], '9')
        self.assertEqual(other['pool']['name'], 'Vest')
        self.assertEqual(other['pool']['division'], '1. Division')
        self.assertEqual([match['kamp_id'] for match in data['matches']], [1])
        self.assertEqual([match['kamp_id'] for match in other['matches']], [2])
        self.assertEqual({event['team'] for event in other['cumulative_points']}, {'C', 'D'})

    def test_merge_preserves_previous_season_and_refreshes_current_entries(self):
        self.seed_pool()
        self.match()
        self.ranking('A', 1, 1, 1, 0, 3, 2, 25, 20, 2)
        self.ranking('B', 2, 1, 0, 1, 2, 3, 20, 25, 1)
        self.output.mkdir()
        history = {
            'metadata': {'seasons': ['2024'], 'league_count': 99, 'pool_count': 99},
            'leagues': [
                {'id': '6', 'name': 'Historic league', 'season_id': '2024', 'raekke_id': 6},
                {'id': '7', 'name': 'Outdated name', 'season_id': '2025', 'raekke_id': 7},
            ],
            'pools': [
                {'id': '41', 'name': 'Historic pool', 'league_id': '6', 'pulje_id': 41},
                {'id': '42', 'name': 'Outdated name', 'league_id': '7', 'pulje_id': 42},
            ],
            'pool_validation': {
                '41': {'mismatch_count': 2, 'affected_teams': 1, 'affected_fields': ['rank']},
                '42': {'mismatch_count': 9, 'affected_teams': 2, 'affected_fields': ['points']},
            },
        }
        index_path = self.output / 'leagues.json'
        index_path.write_text(json.dumps(history), encoding='utf-8')
        historic_file = self.output / '41.json'
        historic_file.write_bytes(b'{"historical": true}\n')
        before = historic_file.read_bytes()
        self.export()
        index = json.loads(index_path.read_text(encoding='utf-8'))
        self.assertEqual(historic_file.read_bytes(), before)
        self.assertEqual(next(row for row in index['pools'] if row['id'] == '41'), history['pools'][0])
        self.assertEqual(next(row for row in index['leagues'] if row['id'] == '6'), history['leagues'][0])
        self.assertEqual(index['metadata']['seasons'], ['2025', '2024'])
        self.assertEqual(index['metadata']['league_count'], 2)
        self.assertEqual(index['metadata']['pool_count'], 2)
        self.assertEqual(index['pool_validation'], {'41': history['pool_validation']['41']})
        self.assertEqual(index['metadata']['validation'], {'pools_with_mismatches': 1, 'mismatch_count': 2})
        self.assertEqual(next(row for row in index['leagues'] if row['id'] == '7')['name'], 'Volleyligaen Herrer')
        self.assertEqual(next(row for row in index['pools'] if row['id'] == '42')['name'], 'Øst')
        self.export()
        repeated = json.loads(index_path.read_text(encoding='utf-8'))
        repeated['metadata']['exported_at'] = index['metadata']['exported_at']
        self.assertEqual(repeated, index)
        self.assertEqual(historic_file.read_bytes(), before)

    def test_merge_handles_legacy_ids_and_updates_retained_pool_league_links(self):
        self.seed_pool()
        self.output.mkdir()
        old_league = '2025:men:volleyligaen'
        old_pool = old_league + ':pulje-42'
        retained_pool = old_league + ':pulje-43'
        history = {
            'leagues': [{'id': old_league, 'name': 'Volleyligaen Herrer', 'season_id': '2025', 'raekke_id': 7}],
            'pools': [
                {'id': old_pool, 'league_id': old_league, 'pulje_id': 42},
                {'id': retained_pool, 'league_id': old_league, 'pulje_id': 43},
            ],
            'pool_validation': {old_pool: {'mismatch_count': 1}, retained_pool: {'mismatch_count': 4}},
        }
        index_path = self.output / 'leagues.json'
        index_path.write_text(json.dumps(history), encoding='utf-8')
        self.export()
        index = json.loads(index_path.read_text(encoding='utf-8'))
        self.assertEqual([row['id'] for row in index['leagues']], ['7'])
        self.assertEqual({row['id'] for row in index['pools']}, {'42', retained_pool})
        self.assertTrue(all(row['league_id'] == '7' for row in index['pools']))
        self.assertEqual(index['pool_validation'], {retained_pool: {'mismatch_count': 4}})

    def test_invalid_existing_index_fails_before_any_export_is_overwritten(self):
        self.seed_pool()
        self.output.mkdir()
        index_path = self.output / 'leagues.json'
        pool_path = self.output / '42.json'
        pool_path.write_bytes(b'previous pool contents')
        self.connection.commit()
        for contents in ('invalid json', '{"leagues": [], "pools": null}'):
            with self.subTest(contents=contents):
                index_path.write_text(contents, encoding='utf-8')
                with self.assertRaises(ValueError):
                    export_json(self.db, self.output)
                self.assertEqual(index_path.read_text(encoding='utf-8'), contents)
                self.assertEqual(pool_path.read_bytes(), b'previous pool contents')

    def test_exporting_empty_database_retains_existing_history(self):
        self.seed_pool()
        self.export()
        index_path = self.output / 'leagues.json'
        before = json.loads(index_path.read_text(encoding='utf-8'))
        pool_before = (self.output / '42.json').read_bytes()
        self.connection.execute('DELETE FROM pools')
        self.connection.execute('DELETE FROM leagues')
        self.connection.commit()
        export_json(self.db, self.output)
        after = json.loads(index_path.read_text(encoding='utf-8'))
        self.assertEqual(after['leagues'], before['leagues'])
        self.assertEqual(after['pools'], before['pools'])
        self.assertEqual(after['metadata']['seasons'], ['2025'])
        self.assertEqual((self.output / '42.json').read_bytes(), pool_before)


if __name__ == '__main__':
    unittest.main()
