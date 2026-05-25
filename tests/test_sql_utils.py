"""
Tests for SQL utilities:
  - split_statements()   from pipeline/transform/sql_utils.py
  - _compute_insert_update() from pipeline/ingest/helpers.py

split_statements must correctly handle comments, dollar-quoting,
string literals, and semicolons inside strings so that multi-statement
SQL files can be executed safely one statement at a time.
"""
import pytest

from pipeline.transform.sql_utils import split_statements
from pipeline.ingest.helpers import _compute_insert_update


# ── split_statements ───────────────────────────────────────────────────────────

class TestSplitStatementsBasic:

    def test_single_statement_no_semicolon(self):
        sql = "SELECT 1"
        result = split_statements(sql)
        assert len(result) == 1
        assert "SELECT 1" in result[0]

    def test_single_statement_with_semicolon(self):
        sql = "SELECT 1;"
        result = split_statements(sql)
        assert len(result) == 1

    def test_two_statements(self):
        sql = "SELECT 1; SELECT 2;"
        result = split_statements(sql)
        assert len(result) == 2

    def test_three_statements(self):
        sql = "SELECT 1; SELECT 2; SELECT 3;"
        result = split_statements(sql)
        assert len(result) == 3

    def test_empty_string_returns_empty_list(self):
        assert split_statements("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert split_statements("   \n\t  ") == []

    def test_only_semicolons_returns_empty_list(self):
        assert split_statements(";;;") == []

    def test_newlines_between_statements(self):
        sql = "SELECT 1;\nSELECT 2;\n"
        result = split_statements(sql)
        assert len(result) == 2


class TestSplitStatementsComments:

    def test_line_comment_only_is_ignored(self):
        sql = "-- This is a comment\n"
        result = split_statements(sql)
        assert result == []

    def test_line_comment_before_statement(self):
        sql = "-- comment\nSELECT 1;"
        result = split_statements(sql)
        assert len(result) == 1

    def test_line_comment_after_statement(self):
        sql = "SELECT 1; -- comment\nSELECT 2;"
        result = split_statements(sql)
        assert len(result) == 2

    def test_block_comment_ignored(self):
        sql = "/* block comment */\nSELECT 1;"
        result = split_statements(sql)
        assert len(result) == 1

    def test_block_comment_inline(self):
        sql = "SELECT /* inline */ 1;"
        result = split_statements(sql)
        assert len(result) == 1

    def test_semicolon_inside_line_comment_not_split(self):
        sql = "-- SELECT 1; fake split\nSELECT 2;"
        result = split_statements(sql)
        assert len(result) == 1

    def test_semicolon_inside_block_comment_not_split(self):
        sql = "/* SELECT 1; fake */ SELECT 2;"
        result = split_statements(sql)
        assert len(result) == 1


class TestSplitStatementsStringLiterals:

    def test_semicolon_in_single_quoted_string(self):
        sql = "INSERT INTO t VALUES ('a;b');"
        result = split_statements(sql)
        assert len(result) == 1

    def test_semicolon_in_double_quoted_identifier(self):
        sql = 'SELECT "col;name" FROM t;'
        result = split_statements(sql)
        assert len(result) == 1

    def test_escaped_quote_in_string(self):
        # Single quote escaped by doubling: 'it''s fine'
        sql = "INSERT INTO t VALUES ('it''s fine');"
        result = split_statements(sql)
        assert len(result) == 1

    def test_multiline_string(self):
        sql = "INSERT INTO t VALUES ('line1\nline2');"
        result = split_statements(sql)
        assert len(result) == 1


class TestSplitStatementsDollarQuoting:

    def test_simple_dollar_quoting(self):
        sql = "CREATE FUNCTION f() RETURNS void AS $$ BEGIN END; $$ LANGUAGE plpgsql;"
        result = split_statements(sql)
        # The semicolon inside $$ should not split
        assert len(result) == 1

    def test_tagged_dollar_quoting(self):
        sql = "CREATE FUNCTION f() RETURNS void AS $body$ BEGIN END; $body$ LANGUAGE plpgsql;"
        result = split_statements(sql)
        assert len(result) == 1

    def test_dollar_quoting_with_semicolons(self):
        sql = """
CREATE OR REPLACE FUNCTION trg_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
        result = split_statements(sql)
        assert len(result) == 1

    def test_multiple_statements_with_dollar_quoting(self):
        sql = """
CREATE FUNCTION f1() RETURNS void AS $$ BEGIN END; $$ LANGUAGE plpgsql;
CREATE FUNCTION f2() RETURNS void AS $$ BEGIN END; $$ LANGUAGE plpgsql;
"""
        result = split_statements(sql)
        assert len(result) == 2


class TestSplitStatementsRealWorldPatterns:

    def test_create_index_pattern(self):
        sql = """
CREATE INDEX IF NOT EXISTS idx_listas_ss_id ON listas_espera_ss_trimestre (ss_id);
CREATE INDEX IF NOT EXISTS idx_listas_trimestre ON listas_espera_ss_trimestre (trimestre);
"""
        result = split_statements(sql)
        assert len(result) == 2

    def test_update_with_where(self):
        sql = """
UPDATE listas_espera_ss_trimestre
SET asimetria = ROUND(promedio_dias - mediana_dias, 1)
WHERE asimetria IS NULL
  AND promedio_dias IS NOT NULL
  AND mediana_dias IS NOT NULL;
"""
        result = split_statements(sql)
        assert len(result) == 1

    def test_alter_table_add_constraint(self):
        sql = """
ALTER TABLE listas_espera_ss_trimestre
ADD CONSTRAINT pk_listas_espera PRIMARY KEY (id);
ALTER TABLE personas_nacional_trimestre
ADD CONSTRAINT pk_personas_nacional PRIMARY KEY (id);
"""
        result = split_statements(sql)
        assert len(result) == 2

    def test_do_block(self):
        sql = """
DO $$
BEGIN
    IF to_regclass('pg_temp._ss_canonicos') IS NULL THEN
        RAISE EXCEPTION 'Table not found';
    END IF;
END;
$$;
"""
        result = split_statements(sql)
        assert len(result) == 1

    def test_returns_list_type(self):
        result = split_statements("SELECT 1;")
        assert isinstance(result, list)

    def test_statements_are_strings(self):
        result = split_statements("SELECT 1; SELECT 2;")
        assert all(isinstance(s, str) for s in result)


# ── _compute_insert_update ─────────────────────────────────────────────────────

class TestComputeInsertUpdate:

    def test_first_load_all_inserts(self):
        # pre_count=0 → nothing existed before → all are inserts
        n_inserted, n_updated = _compute_insert_update(10, 0)
        assert n_inserted == 10
        assert n_updated == 0

    def test_reload_same_data_all_updates(self):
        # pre_count == n_upserted → same rows re-loaded → all are updates
        n_inserted, n_updated = _compute_insert_update(10, 10)
        assert n_inserted == 0
        assert n_updated == 10

    def test_partial_reload(self):
        # 10 rows upserted, 5 existed → 5 inserts + 5 updates
        n_inserted, n_updated = _compute_insert_update(10, 5)
        assert n_inserted == 5
        assert n_updated == 5

    def test_more_pre_than_upserted(self):
        # If somehow pre > upserted, n_updated capped at n_upserted
        n_inserted, n_updated = _compute_insert_update(5, 20)
        assert n_inserted == 0
        assert n_updated == 5

    def test_zero_upserted(self):
        n_inserted, n_updated = _compute_insert_update(0, 0)
        assert n_inserted == 0
        assert n_updated == 0

    def test_total_equals_upserted(self):
        # Invariant: n_inserted + n_updated == n_upserted always
        for n, pre in [(10, 0), (10, 10), (10, 5), (5, 20), (0, 0), (100, 50)]:
            n_inserted, n_updated = _compute_insert_update(n, pre)
            assert n_inserted + n_updated == n, (
                f"Failed for n={n}, pre={pre}: {n_inserted} + {n_updated} != {n}"
            )

    def test_return_types_are_int(self):
        n_inserted, n_updated = _compute_insert_update(10, 5)
        assert isinstance(n_inserted, int)
        assert isinstance(n_updated, int)

    def test_large_numbers(self):
        n_inserted, n_updated = _compute_insert_update(1_000_000, 400_000)
        assert n_inserted == 600_000
        assert n_updated == 400_000