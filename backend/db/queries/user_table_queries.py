from geonature.utils.env import DB
import pdb

def delete_table(full_table_name):
    DB.session.begin(subtransactions=True)
    try:        
        DB.session.execute("""
            DROP TABLE {};
            """.format(full_table_name))
        DB.session.commit()
    except Exception:
        DB.session.rollback()
        raise


def rename_table(schema_name, original_name, new_name):
    DB.session.begin(subtransactions=True)
    try:
        DB.session.execute("""
            ALTER TABLE {schema_name}.{original_name} 
            RENAME TO {new_name};
            """.format(
                schema_name = schema_name, 
                original_name = original_name, 
                new_name = new_name))
        DB.session.commit()
    except Exception:
        DB.session.rollback()
        raise

def set_primary_key(schema_name, table_name, pk_col_name):
    DB.session.begin(subtransactions=True)
    try:
        DB.session.execute("""
            ALTER TABLE ONLY {schema_name}.{table_name} 
            ADD CONSTRAINT pk_{schema_name}_{table_name} PRIMARY KEY ({pk_col_name});
            """.format(
                schema_name = schema_name, 
                table_name = table_name, 
                pk_col_name = pk_col_name))
        DB.session.commit()
    except Exception:
        DB.session.rollback()
        raise


def alter_column_type(schema_name, table_name, col_name, col_type):
    DB.session.begin(subtransactions=True)
    try:
        DB.session.execute("""
            ALTER TABLE {schema_name}.{table_name}
            ALTER COLUMN {col_name} 
            TYPE {col_type} USING {col_name}::{col_type};
            """.format(
                schema_name = schema_name, 
                table_name = table_name,
                col_name = col_name,
                col_type = col_type))
        DB.session.commit()
    except Exception:
        DB.session.rollback()
        raise


def get_n_loaded_rows(full_table_name):
    try:
        n_loaded_rows = DB.session.execute("""
            SELECT count(*) 
            FROM {};
            """.format(full_table_name)
            ).fetchone()[0]
        return n_loaded_rows
    except Exception:
        raise


def get_n_invalid_rows(full_table_name):
    try:
        n_invalid_rows = DB.session.execute("""
            SELECT count(*) 
            FROM {} WHERE gn_is_valid = 'False';
            """.format(full_table_name)).fetchone()[0]
        return n_invalid_rows
    except Exception:
        raise


def get_n_valid_rows(schema_name, table_name):
    try:
        n_valid_rows = DB.session.execute("""
            SELECT count(*)
            FROM {schema_name}.{table_name}
            WHERE gn_is_valid = 'True';
            """.format(
                schema_name = schema_name,
                table_name = table_name
            )).fetchone()[0]
        return n_valid_rows
    except Exception:
        raise


def get_n_taxa(schema_name, table_name, cd_nom_col):
    try:
        n_taxa = DB.session.execute("""
            SELECT COUNT(DISTINCT {cd_nom_col})
            FROM {schema_name}.{table_name}
            WHERE gn_is_valid = 'True';
            """.format(
                schema_name = schema_name,
                table_name = table_name,
                cd_nom_col = cd_nom_col
            )).fetchone()[0]
        return n_taxa
    except Exception:
        raise


def get_date_ext(schema_name, table_name, date_min_col, date_max_col):
    try:
        dates = DB.session.execute("""
            SELECT min(date_debut), max(date_fin)
            FROM {schema_name}.{table_name}
            WHERE gn_is_valid = 'True';
            """.format(
                schema_name = schema_name,
                table_name = table_name,
                date_min_col = date_min_col,
                date_max_col = date_max_col
            )).fetchall()[0]
        
        return {
            'date_min': dates[0],
            'date_max': dates[1]
        }
    except Exception:
        raise