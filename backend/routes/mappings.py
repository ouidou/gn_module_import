from flask import Blueprint, request, jsonify, send_file, current_app

from utils_flask_sqla.response import json_resp
from geonature.utils.env import DB
from geonature.core.gn_permissions import decorators as permissions

from ..db.models import (
    TImports,
    TMappings,
    CorRoleMapping,
    TMappingsFields,
)

from ..db.queries.user_table_queries import (
    get_table_info,
    get_table_names,
    get_row_number,
    get_n_invalid_rows,
)

from ..db.queries.metadata import get_id_field_mapping

from ..db.queries.nomenclatures import get_content_mapping

from ..db.queries.save_mapping import get_selected_columns

from ..utils.clean_names import *
from ..utils.utils import get_pk_name

from ..upload.upload_errors import *


from ..transform.nomenclatures.nomenclatures import get_nomenc_info

from ..logs import logger
from ..api_error import GeonatureImportApiError
from ..blueprint import blueprint


@blueprint.route("/mappings/<mapping_type>/<import_id>", methods=["GET"])
@permissions.check_cruved_scope("C", True, module_code="IMPORT")
@json_resp
def get_mappings(info_role, mapping_type, import_id):
    """
        Load mapping names in frontend (select)
    """

    try:
        results = (
            DB.session.query(TMappings)
            .filter(CorRoleMapping.id_role == info_role.id_role)
            .filter(TMappings.mapping_type == mapping_type.upper())
            .all()
        )

        mappings = []

        if len(results) > 0:
            for row in results:
                d = {"id_mapping": row.id_mapping, "mapping_label": row.mapping_label}
                mappings.append(d)
        else:
            mappings.append("empty")

        logger.debug("List of mappings %s", mappings)

        # get column names
        col_names = "undefined import_id"
        if import_id not in ["undefined", "null"]:
            ARCHIVES_SCHEMA_NAME = blueprint.config["ARCHIVES_SCHEMA_NAME"]
            IMPORTS_SCHEMA_NAME = blueprint.config["IMPORTS_SCHEMA_NAME"]
            table_names = get_table_names(
                ARCHIVES_SCHEMA_NAME, IMPORTS_SCHEMA_NAME, int(import_id)
            )
            col_names = get_table_info(
                table_names["imports_table_name"], info="column_name"
            )
            col_names.remove("gn_is_valid")
            col_names.remove("gn_invalid_reason")
            col_names.remove(get_pk_name(blueprint.config["PREFIX"]))

        return {"mappings": mappings, "column_names": col_names}, 200
    except Exception as e:
        raise GeonatureImportApiError(
            message="INTERNAL SERVER ERROR - get_mappings() error : contactez l'administrateur du site",
            details=str(e),
        )


@blueprint.route("/field_mappings/<id_mapping>", methods=["GET"])
@permissions.check_cruved_scope("C", True, module_code="IMPORT")
@json_resp
def get_mapping_fields(info_role, id_mapping):
    """
        load source and target fields from an id_mapping
    """

    try:
        logger.debug("get fields saved in id_mapping = %s", id_mapping)

        fields = (
            DB.session.query(TMappingsFields)
            .filter(TMappingsFields.id_mapping == int(id_mapping))
            .filter(TMappingsFields.is_selected)
            .all()
        )

        mapping_fields = []

        if len(fields) > 0:
            for field in fields:
                if not field.is_selected:
                    source_field = ""
                else:
                    source_field = field.source_field
                d = {
                    "id_match_fields": field.id_match_fields,
                    "id_mapping": field.id_mapping,
                    "source_field": field.source_field,
                    "target_field": field.target_field,
                }
                mapping_fields.append(d)
        else:
            mapping_fields.append("empty")

        logger.debug(
            "mapping_fields = %s from id_mapping number %s", mapping_fields, id_mapping
        )

        return mapping_fields, 200

    except Exception as e:
        raise GeonatureImportApiError(
            message="INTERNAL SERVER ERROR - get_mapping_fields() error : contactez l'administrateur du site",
            details=str(e),
        )


@blueprint.route("/content_mappings/<id_mapping>", methods=["GET"])
@permissions.check_cruved_scope("C", True, module_code="IMPORT")
@json_resp
def get_mapping_contents(info_role, id_mapping):
    """
        load source and target contents from an id_mapping
    """

    try:
        logger.debug("get contents saved in id_mapping = %s", id_mapping)
        content_map = get_content_mapping(id_mapping)
        return content_map, 200
    except Exception as e:
        raise GeonatureImportApiError(
            message="INTERNAL SERVER ERROR - get_mapping_contents() error : contactez l'administrateur du site",
            details=str(e),
        )


@blueprint.route("/mappingName", methods=["GET", "POST"])
@permissions.check_cruved_scope("C", True, module_code="IMPORT")
@json_resp
def postMappingName(info_role):
    try:
        logger.info("Posting mapping field name")

        data = request.form.to_dict()

        if data["mappingName"] == "" or data["mappingName"] == "null":
            return "Vous devez donner un nom au mapping", 400

        # check if name already exists
        names_request = DB.session.query(TMappings).all()
        names = [name.mapping_label for name in names_request]

        if data["mappingName"] in names:
            return "Ce nom de mapping existe déjà", 400

        # fill BibMapping
        new_name = TMappings(
            mapping_label=data["mappingName"],
            mapping_type=data["mapping_type"],
            active=True,
        )

        DB.session.add(new_name)
        DB.session.flush()

        # fill CorRoleMapping

        id_mapping = (
            DB.session.query(TMappings.id_mapping)
            .filter(TMappings.mapping_label == data["mappingName"])
            .one()[0]
        )

        new_map_role = CorRoleMapping(id_role=info_role.id_role, id_mapping=id_mapping)

        DB.session.add(new_map_role)
        DB.session.commit()

        logger.info("-> Mapping field name posted")

        return id_mapping, 200

    except Exception as e:
        logger.error("*** ERROR WHEN POSTING MAPPING FIELD NAME")
        logger.exception(e)
        DB.session.rollback()
        raise GeonatureImportApiError(
            message="INTERNAL SERVER ERROR - posting mapping field name : contactez l'administrateur du site",
            details=str(e),
        )
    finally:
        DB.session.close()


@blueprint.route("/bibFields", methods=["GET"])
@permissions.check_cruved_scope("C", True, module_code="IMPORT")
@json_resp
def get_dict_fields(info_role):
    """
    Get all synthese fields
    Use in field mapping steps
    """
    try:

        IMPORTS_SCHEMA_NAME = blueprint.config["IMPORTS_SCHEMA_NAME"]

        bibs = DB.session.execute(
            """
            SELECT *
            FROM {schema_name}.dict_fields fields
            JOIN {schema_name}.dict_themes themes on fields.id_theme = themes.id_theme
            WHERE fields.display = true
            ORDER BY fields.order_field ASC;
            """.format(
                schema_name=IMPORTS_SCHEMA_NAME
            )
        ).fetchall()

        max_theme = DB.session.execute(
            """
            SELECT max(id_theme)
            FROM {schema_name}.dict_fields fields
            """.format(
                schema_name=IMPORTS_SCHEMA_NAME
            )
        ).fetchone()[0]

        data_theme = []
        for i in range(max_theme):
            data = []
            for row in bibs:
                if row.id_theme == i + 1:
                    theme_name = row.fr_label_theme
                    d = {
                        "id_field": row.id_field,
                        "name_field": row.name_field,
                        "required": row.mandatory,
                        "fr_label": row.fr_label,
                        "autogenerated": row.autogenerated,
                    }
                    data.append(d)
            data_theme.append({"theme_name": theme_name, "fields": data})

        return data_theme, 200

    except Exception as e:
        logger.error("*** SERVER ERROR WHEN GETTING DICT_FIELDS AND DICT_THEMES")
        logger.exception(e)
        raise GeonatureImportApiError(
            message="INTERNAL SERVER ERROR when getting dict_fields and dict_themes",
            details=str(e),
        )


@blueprint.route("/getNomencInfo/<import_id>", methods=["GET", "POST"])
@permissions.check_cruved_scope("C", True, module_code="IMPORT")
@json_resp
def getNomencInfo(info_role, import_id):
    """
        Get all nomenclature info for a mapping
        Use for the value mapping step
    """
    try:
        # get table_name
        IMPORTS_SCHEMA_NAME = blueprint.config["IMPORTS_SCHEMA_NAME"]
        ARCHIVES_SCHEMA_NAME = blueprint.config["ARCHIVES_SCHEMA_NAME"]
        table_names = get_table_names(
            ARCHIVES_SCHEMA_NAME, IMPORTS_SCHEMA_NAME, int(import_id)
        )
        table_name = table_names["imports_table_name"]

        id_mapping = get_id_field_mapping(import_id)
        selected_columns = get_selected_columns(id_mapping)

        nomenc_info = get_nomenc_info(selected_columns, IMPORTS_SCHEMA_NAME, table_name)

        return {"content_mapping_info": nomenc_info}, 200
    except Exception as e:
        logger.error("*** ERROR WHEN GETTING NOMENCLATURE")
        logger.exception(e)
        DB.session.rollback()
        raise GeonatureImportApiError(
            message="INTERNAL SERVER ERROR : Erreur pour obtenir les infos de nomenclature - \
            contacter l'administrateur",
            details=str(e),
        )
    finally:
        DB.session.close()


@blueprint.route("/postMetaToStep3", methods=["GET", "POST"])
@permissions.check_cruved_scope("C", True, module_code="IMPORT")
@json_resp
def postMetaToStep3(info_role):
    try:

        data = request.form.to_dict()

        ### CHECK VALIDITY

        ARCHIVES_SCHEMA_NAME = blueprint.config["ARCHIVES_SCHEMA_NAME"]
        IMPORTS_SCHEMA_NAME = blueprint.config["IMPORTS_SCHEMA_NAME"]
        table_names = get_table_names(
            ARCHIVES_SCHEMA_NAME, IMPORTS_SCHEMA_NAME, int(data["import_id"])
        )
        full_imports_table_name = table_names["imports_full_table_name"]

        row_count = get_row_number(full_imports_table_name)
        row_error_count = get_n_invalid_rows(full_imports_table_name)
        if row_error_count == row_count:
            return (
                {
                    "message": "Toutes vos observations comportent des erreurs : \
                    vous ne pouvez pas accéder à l'étape suivante"
                },
                400,
            )

        # UPDATE TIMPORTS

        logger.info("update t_imports from step 2 to step 3")

        DB.session.query(TImports).filter(
            TImports.id_import == int(data["import_id"])
        ).update({TImports.step: 3})

        DB.session.commit()

        return (
            {
                "table_name": table_names["imports_table_name"],
                "import_id": data["import_id"],
            },
            200,
        )
    except Exception as e:
        logger.error("*** ERROR IN STEP 2 NEXT BUTTON")
        logger.exception(e)
        DB.session.rollback()
        raise GeonatureImportApiError(
            message="INTERNAL SERVER ERROR : Erreur pendant le passage vers l'étape 3 - contacter l'administrateur",
            details=str(e),
        )
    finally:
        DB.session.close()