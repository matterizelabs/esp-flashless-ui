idf_component_register()

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
