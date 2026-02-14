idf_component_register()

# ESP-IDF 5.x does not auto-load idf.py extensions from managed components.
# To keep `idf.py flashless --no-build` working without manual env setup,
# bootstrap a project-level idf_ext.py loader when one is not already present.
set(_flashless_project_ext "${PROJECT_DIR}/idf_ext.py")
if(NOT EXISTS "${_flashless_project_ext}")
    configure_file(
        "${COMPONENT_DIR}/tools/flashless/project_idf_ext.py"
        "${_flashless_project_ext}"
        COPYONLY)
    message(STATUS "flashless: generated ${_flashless_project_ext} for idf.py action auto-load")
endif()

# Fallback for ESP-IDF versions that do not auto-load idf.py extensions
# from components. Running `idf.py flashless` still works as a build target.
if(NOT TARGET flashless)
    idf_build_get_property(_idf_python PYTHON)
    if(NOT _idf_python)
        set(_idf_python ${PYTHON})
    endif()
    if(NOT _idf_python)
        set(_idf_python python)
    endif()

    add_custom_target(flashless
        COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${COMPONENT_DIR}/tools:$ENV{PYTHONPATH}"
                ${_idf_python}
                -m flashless.cli
                run
                --project-dir ${PROJECT_DIR}
                --build-dir ${BUILD_DIR}
        USES_TERMINAL
        VERBATIM)
endif()
