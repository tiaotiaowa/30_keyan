#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Topology Verification Script
验证实体对数据中拓扑关系的空间正确性
"""

import json
import random
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# Data paths
POSITIVE_PATH = 'D:/gis_data/output/pairs_positive.jsonl'
NEGATIVE_PATH = 'D:/gis_data/output/pairs_negative.jsonl'

# PostGIS connection config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'geokd_sr',
    'user': 'postgres',
    'password': '19950625'
}


class TopologyValidator:
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.conn = None
        self.cursor = None
        self.results = defaultdict(lambda: {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'failures': []
        })

    def connect(self):
        """Connect to PostGIS database"""
        self.conn = psycopg2.connect(**self.db_config)
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        print("PostGIS database connected successfully")

    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def check_contains(self, a_id: str, b_id: str, a_type: str, b_type: str) -> Tuple[bool, str]:
        """
        Verify contains relation: ST_Contains(a.geom, b.centroid)
        For province-city use centroid contains, for Point types use point contains
        """
        if b_type in ['station', 'peak', 'pass', 'lake']:
            # Point type - check contains directly
            query = """
                SELECT ST_Contains(a.geom, b.centroid) as contains_result,
                       ST_Contains(a.geom, b.geom) as contains_geom
                FROM geokr_entity a, geokr_entity b
                WHERE a.entity_id = %s AND b.entity_id = %s
            """
        else:
            # Polygon type - check centroid contains
            query = """
                SELECT ST_Contains(a.geom, b.centroid) as contains_result
                FROM geokr_entity a, geokr_entity b
                WHERE a.entity_id = %s AND b.entity_id = %s
            """

        self.cursor.execute(query, (a_id, b_id))
        result = self.cursor.fetchone()
        return bool(result['contains_result']) if result else False, ""

    def check_within(self, a_id: str, b_id: str) -> Tuple[bool, str]:
        """
        Verify within relation: ST_Contains(b.geom, a.centroid)
        """
        query = """
            SELECT ST_Contains(b.geom, a.centroid) as within_result
            FROM geokr_entity a, geokr_entity b
            WHERE a.entity_id = %s AND b.entity_id = %s
        """
        self.cursor.execute(query, (a_id, b_id))
        result = self.cursor.fetchone()
        return bool(result['within_result']) if result else False, ""

    def check_touches(self, a_id: str, b_id: str) -> Tuple[bool, str]:
        """
        Verify touches relation: ST_Touches(a.geom, b.geom)
        """
        query = """
            SELECT ST_Touches(a.geom, b.geom) as touches_result
            FROM geokr_entity a, geokr_entity b
            WHERE a.entity_id = %s AND b.entity_id = %s
        """
        self.cursor.execute(query, (a_id, b_id))
        result = self.cursor.fetchone()
        return bool(result['touches_result']) if result else False, ""

    def check_crosses(self, a_id: str, b_id: str) -> Tuple[bool, str]:
        """
        Verify crosses relation: ST_Crosses(a.geom, b.geom)
        """
        query = """
            SELECT ST_Crosses(a.geom, b.geom) as crosses_result
            FROM geokr_entity a, geokr_entity b
            WHERE a.entity_id = %s AND b.entity_id = %s
        """
        self.cursor.execute(query, (a_id, b_id))
        result = self.cursor.fetchone()
        return bool(result['crosses_result']) if result else False, ""

    def check_disjoint(self, a_id: str, b_id: str) -> Tuple[bool, str]:
        """
        Verify disjoint relation: ST_Disjoint(a.geom, b.geom)
        """
        query = """
            SELECT ST_Disjoint(a.geom, b.geom) as disjoint_result
            FROM geokr_entity a, geokr_entity b
            WHERE a.entity_id = %s AND b.entity_id = %s
        """
        self.cursor.execute(query, (a_id, b_id))
        result = self.cursor.fetchone()
        return bool(result['disjoint_result']) if result else False, ""

    def check_distance(self, a_id: str, b_id: str, expected_distance: float) -> Tuple[bool, str, float]:
        """
        Verify distance calculation: ST_DistanceSphere
        Returns: (passed, info, actual_distance)
        """
        query = """
            SELECT ST_DistanceSphere(a.centroid, b.centroid) / 1000.0 as distance_km
            FROM geokr_entity a, geokr_entity b
            WHERE a.entity_id = %s AND b.entity_id = %s
        """
        self.cursor.execute(query, (a_id, b_id))
        result = self.cursor.fetchone()
        if result:
            actual_distance = result['distance_km']
            error = abs(actual_distance - expected_distance)
            passed = error < 1.0  # Error should be < 1km
            info = f"Expected: {expected_distance:.2f}km, Actual: {actual_distance:.2f}km, Error: {error:.2f}km"
            return passed, info, actual_distance
        return False, "Cannot calculate distance", 0.0

    def record_result(self, category: str, passed: bool, failure_info: Dict = None):
        """Record verification result"""
        self.results[category]['total'] += 1
        if passed:
            self.results[category]['passed'] += 1
        else:
            self.results[category]['failed'] += 1
            if failure_info:
                self.results[category]['failures'].append(failure_info)

    def load_data(self, filepath: str) -> List[Dict]:
        """Load JSONL data"""
        data = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line))
        return data

    def verify_contains_positive(self, data: List[Dict], n: int = 50):
        """Verify contains positive samples"""
        print(f"\n{'='*60}")
        print(f"1. Verify contains positive (n={n})")
        print(f"{'='*60}")

        contains_data = [d for d in data if d.get('target_relation') == 'topological.contains']
        sample = random.sample(contains_data, min(n, len(contains_data)))

        for record in sample:
            a_id = record['entity_a']['entity_id']
            b_id = record['entity_b']['entity_id']
            a_type = record['entity_a']['type']
            b_type = record['entity_b']['type']

            passed, _ = self.check_contains(a_id, b_id, a_type, b_type)

            if not passed:
                self.record_result('contains_positive', False, {
                    'pair_id': record['pair_id'],
                    'a_id': a_id,
                    'b_id': b_id,
                    'a_name': record['entity_a'].get('name_zh', ''),
                    'b_name': record['entity_b'].get('name_zh', ''),
                    'a_type': a_type,
                    'b_type': b_type
                })
            else:
                self.record_result('contains_positive', True)

    def verify_within_positive(self, data: List[Dict], n: int = 50):
        """Verify within positive samples"""
        print(f"\n{'='*60}")
        print(f"2. Verify within positive (n={n})")
        print(f"{'='*60}")

        within_data = [d for d in data if d.get('target_relation') == 'topological.within']
        sample = random.sample(within_data, min(n, len(within_data)))

        for record in sample:
            a_id = record['entity_a']['entity_id']
            b_id = record['entity_b']['entity_id']

            passed, _ = self.check_within(a_id, b_id)

            if not passed:
                self.record_result('within_positive', False, {
                    'pair_id': record['pair_id'],
                    'a_id': a_id,
                    'b_id': b_id,
                    'a_name': record['entity_a'].get('name_zh', ''),
                    'b_name': record['entity_b'].get('name_zh', '')
                })
            else:
                self.record_result('within_positive', True)

    def verify_touches_positive(self, data: List[Dict], n: int = 50):
        """Verify touches positive samples"""
        print(f"\n{'='*60}")
        print(f"3. Verify touches positive (n={n})")
        print(f"{'='*60}")

        touches_data = [d for d in data if d.get('target_relation') == 'topological.touches']
        sample = random.sample(touches_data, min(n, len(touches_data)))

        for record in sample:
            a_id = record['entity_a']['entity_id']
            b_id = record['entity_b']['entity_id']

            passed, _ = self.check_touches(a_id, b_id)

            if not passed:
                self.record_result('touches_positive', False, {
                    'pair_id': record['pair_id'],
                    'a_id': a_id,
                    'b_id': b_id,
                    'a_name': record['entity_a'].get('name_zh', ''),
                    'b_name': record['entity_b'].get('name_zh', '')
                })
            else:
                self.record_result('touches_positive', True)

    def verify_crosses_positive(self, data: List[Dict], n: int = 50):
        """Verify crosses positive samples"""
        print(f"\n{'='*60}")
        print(f"4. Verify crosses positive (n={n})")
        print(f"{'='*60}")

        crosses_data = [d for d in data if d.get('target_relation') == 'topological.crosses']
        sample = random.sample(crosses_data, min(n, len(crosses_data)))

        for record in sample:
            a_id = record['entity_a']['entity_id']
            b_id = record['entity_b']['entity_id']

            passed, _ = self.check_crosses(a_id, b_id)

            if not passed:
                self.record_result('crosses_positive', False, {
                    'pair_id': record['pair_id'],
                    'a_id': a_id,
                    'b_id': b_id,
                    'a_name': record['entity_a'].get('name_zh', ''),
                    'b_name': record['entity_b'].get('name_zh', '')
                })
            else:
                self.record_result('crosses_positive', True)

    def verify_disjoint_positive(self, data: List[Dict], n: int = 50):
        """Verify disjoint positive samples"""
        print(f"\n{'='*60}")
        print(f"5. Verify disjoint positive (n={n})")
        print(f"{'='*60}")

        disjoint_data = [d for d in data if d.get('target_relation') == 'topological.disjoint']
        sample = random.sample(disjoint_data, min(n, len(disjoint_data)))

        for record in sample:
            a_id = record['entity_a']['entity_id']
            b_id = record['entity_b']['entity_id']

            passed, _ = self.check_disjoint(a_id, b_id)

            if not passed:
                self.record_result('disjoint_positive', False, {
                    'pair_id': record['pair_id'],
                    'a_id': a_id,
                    'b_id': b_id,
                    'a_name': record['entity_a'].get('name_zh', ''),
                    'b_name': record['entity_b'].get('name_zh', '')
                })
            else:
                self.record_result('disjoint_positive', True)

    def verify_composite_within(self, data: List[Dict], n_per_category: int = 10):
        """
        Verify within in composite relations
        C2: composite.direction_distance_topology
        C3: composite.direction_topology
        C4: composite.distance_topology
        """
        print(f"\n{'='*60}")
        print(f"6. Verify composite within (n={n_per_category} per category)")
        print(f"{'='*60}")

        categories = {
            'C2': 'composite.direction_distance_topology',
            'C3': 'composite.direction_topology',
            'C4': 'composite.distance_topology'
        }

        for cat_code, relation_type in categories.items():
            cat_data = [d for d in data if d.get('target_relation') == relation_type]
            if len(cat_data) >= n_per_category:
                sample = random.sample(cat_data, n_per_category)
                category_key = f'composite_within_{cat_code}'

                for record in sample:
                    a_id = record['entity_a']['entity_id']
                    b_id = record['entity_b']['entity_id']

                    passed, _ = self.check_within(a_id, b_id)

                    if not passed:
                        self.record_result(category_key, False, {
                            'pair_id': record['pair_id'],
                            'a_id': a_id,
                            'b_id': b_id,
                            'a_name': record['entity_a'].get('name_zh', ''),
                            'b_name': record['entity_b'].get('name_zh', ''),
                            'category': cat_code
                        })
                    else:
                        self.record_result(category_key, True)

    def verify_negative(self, data: List[Dict], n_per_type: int = 20):
        """Verify negative samples"""
        print(f"\n{'='*60}")
        print(f"7. Verify negative samples (n={n_per_type} per type)")
        print(f"{'='*60}")

        # contains negative
        contains_neg = [d for d in data if d.get('target_relation') == 'topological.contains']
        if contains_neg:
            sample = random.sample(contains_neg, min(n_per_type, len(contains_neg)))
            for record in sample:
                a_id = record['entity_a']['entity_id']
                b_id = record['entity_b']['entity_id']
                a_type = record['entity_a']['type']
                b_type = record['entity_b']['type']

                passed, _ = self.check_contains(a_id, b_id, a_type, b_type)
                # Negative should return False
                if passed:
                    self.record_result('negative_contains', False, {
                        'pair_id': record['pair_id'],
                        'a_id': a_id,
                        'b_id': b_id,
                        'a_name': record['entity_a'].get('name_zh', ''),
                        'b_name': record['entity_b'].get('name_zh', ''),
                        'reason': 'Negative contains but actually True'
                    })
                else:
                    self.record_result('negative_contains', True)

        # crosses negative
        crosses_neg = [d for d in data if d.get('target_relation') == 'topological.crosses']
        if crosses_neg:
            sample = random.sample(crosses_neg, min(n_per_type, len(crosses_neg)))
            for record in sample:
                a_id = record['entity_a']['entity_id']
                b_id = record['entity_b']['entity_id']

                passed, _ = self.check_crosses(a_id, b_id)
                if passed:
                    self.record_result('negative_crosses', False, {
                        'pair_id': record['pair_id'],
                        'a_id': a_id,
                        'b_id': b_id,
                        'a_name': record['entity_a'].get('name_zh', ''),
                        'b_name': record['entity_b'].get('name_zh', ''),
                        'reason': 'Negative crosses but actually True'
                    })
                else:
                    self.record_result('negative_crosses', True)

        # C2/C3/C4 negative
        categories = {
            'C2': 'composite.direction_distance_topology',
            'C3': 'composite.direction_topology',
            'C4': 'composite.distance_topology'
        }

        for cat_code, relation_type in categories.items():
            cat_data = [d for d in data if d.get('target_relation') == relation_type]
            if len(cat_data) >= n_per_type:
                sample = random.sample(cat_data, n_per_type)
                category_key = f'negative_within_{cat_code}'

                for record in sample:
                    a_id = record['entity_a']['entity_id']
                    b_id = record['entity_b']['entity_id']

                    passed, _ = self.check_within(a_id, b_id)
                    # Negative should return False
                    if passed:
                        self.record_result(category_key, False, {
                            'pair_id': record['pair_id'],
                            'a_id': a_id,
                            'b_id': b_id,
                            'a_name': record['entity_a'].get('name_zh', ''),
                            'b_name': record['entity_b'].get('name_zh', ''),
                            'reason': f'Negative {cat_code} within but actually True'
                        })
                    else:
                        self.record_result(category_key, True)

    def verify_distance(self, data: List[Dict], n: int = 30):
        """Verify distance calculation"""
        print(f"\n{'='*60}")
        print(f"8. Verify distance calculation (n={n})")
        print(f"{'='*60}")

        # Find records with distance_km info
        distance_data = []
        for d in data:
            if 'distance_km' in d.get('spatial_facts', {}):
                distance_data.append(d)

        sample = random.sample(distance_data, min(n, len(distance_data)))

        for record in sample:
            a_id = record['entity_a']['entity_id']
            b_id = record['entity_b']['entity_id']
            expected = record['spatial_facts']['distance_km']

            passed, info, _ = self.check_distance(a_id, b_id, expected)

            if not passed:
                self.record_result('distance', False, {
                    'pair_id': record['pair_id'],
                    'a_id': a_id,
                    'b_id': b_id,
                    'a_name': record['entity_a'].get('name_zh', ''),
                    'b_name': record['entity_b'].get('name_zh', ''),
                    'info': info
                })
            else:
                self.record_result('distance', True)

    def print_summary(self):
        """Print verification summary"""
        print(f"\n{'='*60}")
        print("Verification Summary")
        print(f"{'='*60}")

        # Build result groups
        positive_cats = ['contains_positive', 'within_positive', 'touches_positive',
                       'crosses_positive', 'disjoint_positive']
        composite_cats = [f'composite_within_{c}' for c in ['C2', 'C3', 'C4']]
        negative_cats = ['negative_contains', 'negative_crosses']
        negative_cats.extend([f'negative_within_{c}' for c in ['C2', 'C3', 'C4']])
        distance_cats = ['distance']

        all_groups = [
            ("Positive Verification", positive_cats),
            ("Composite Verification", composite_cats),
            ("Negative Verification", negative_cats),
            ("Distance Verification", distance_cats)
        ]

        overall_total = 0
        overall_passed = 0

        for group_name, categories in all_groups:
            print(f"\n[{group_name}]")
            for cat in categories:
                if cat in self.results:
                    r = self.results[cat]
                    total = r['total']
                    passed = r['passed']
                    failed = r['failed']
                    rate = (passed / total * 100) if total > 0 else 0
                    print(f"  {cat}: {passed}/{total} passed ({rate:.1f}%)")

                    overall_total += total
                    overall_passed += passed

                    # Show failure samples
                    if r['failures']:
                        print(f"    Failures:")
                        for f in r['failures'][:5]:
                            print(f"      - {f}")

        print(f"\n{'='*60}")
        print(f"Overall Pass Rate: {overall_passed}/{overall_total} ({overall_passed/overall_total*100:.1f}%)")
        print(f"{'='*60}")


def main():
    random.seed(42)  # Set random seed for reproducibility

    validator = TopologyValidator(DB_CONFIG)
    validator.connect()

    try:
        # Load data
        print("Loading data...")
        positive_data = validator.load_data(POSITIVE_PATH)
        negative_data = validator.load_data(NEGATIVE_PATH)
        print(f"Positive samples: {len(positive_data)}")
        print(f"Negative samples: {len(negative_data)}")

        # Run verification
        validator.verify_contains_positive(positive_data, n=50)
        validator.verify_within_positive(positive_data, n=50)
        validator.verify_touches_positive(positive_data, n=50)
        validator.verify_crosses_positive(positive_data, n=50)
        validator.verify_disjoint_positive(positive_data, n=50)
        validator.verify_composite_within(positive_data, n_per_category=10)
        validator.verify_negative(negative_data, n_per_type=20)
        validator.verify_distance(positive_data, n=30)

        # Print summary
        validator.print_summary()

    finally:
        validator.close()


if __name__ == '__main__':
    main()
