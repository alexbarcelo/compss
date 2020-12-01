source "${COMPSS_HOME}/Runtime/scripts/system/commons/logger.sh"

###############################################
###############################################
#            CONSTANTS DEFINITION
###############################################
###############################################

#----------------------------------------------
# DEFAULT VALUES
#----------------------------------------------
# Available Schedulers
DATA_SCHEDULER=es.bsc.compss.scheduler.fifodatalocation.FIFODataLocationScheduler
FIFO_SCHEDULER=es.bsc.compss.scheduler.fifonew.FIFOScheduler
FIFO_DATA_SCHEDULER=es.bsc.compss.scheduler.fifodatanew.FIFODataScheduler
LIFO_SCHEDULER=es.bsc.compss.scheduler.lifonew.LIFOScheduler
BASE_SCHEDULER=es.bsc.compss.components.impl.TaskScheduler
LOAD_BALANCING_SCHEDULER=es.bsc.compss.scheduler.loadbalancing.LoadBalancingScheduler

DEFAULT_SCHEDULER=${LOAD_BALANCING_SCHEDULER}

# Available Cloud Connector
DEFAULT_SSH_CONNECTOR="es.bsc.compss.connectors.DefaultSSHConnector"
DEFAULT_NO_SSH_CONNECTOR="es.bsc.compss.connectors.DefaultNoSSHConnector"

DEFAULT_CONNECTOR=${DEFAULT_SSH_CONNECTOR}

DEFAULT_EXTERNAL_ADAPTATION=false

#----------------------------------------------
# ERROR MESSAGES
#----------------------------------------------


###############################################
###############################################
#        SCHEDULER HANDLING FUNCTIONS
###############################################
###############################################
#----------------------------------------------
# CHECK SCHEDULER-RELATED ENV VARIABLES
#----------------------------------------------
check_scheduler_env() {
  # Configuration files
  if [ -z "$DEFAULT_PROJECT" ]; then
    DEFAULT_PROJECT=${COMPSS_HOME}/Runtime/configuration/xml/projects/default_project.xml
  fi

  if [ -z "$DEFAULT_RESOURCES" ]; then
    DEFAULT_RESOURCES=${COMPSS_HOME}/Runtime/configuration/xml/resources/default_resources.xml
  fi

}


#----------------------------------------------
# CHECK SCHEDULER-RELATED SETUP values
#----------------------------------------------
check_scheduler_setup () {
  if [ -z "$projFile" ]; then
    display_info "Using default location for project file: ${DEFAULT_PROJECT}"
    projFile=${DEFAULT_PROJECT}
  fi

  if [ -z "$resFile" ]; then
    display_info "Using default location for resources file: ${DEFAULT_RESOURCES}"
    resFile=${DEFAULT_RESOURCES}
  fi

  # Scheduler
  if [ -z "$scheduler" ]; then
    scheduler=${DEFAULT_SCHEDULER}
  fi

  # input_profile, output_profile and scheduler_config are variables potentially empty

  if [ -z "$conn" ]; then
    conn=${DEFAULT_CONNECTOR}
  fi
  
  if [ -z "$external_adaptation" ]; then
	  external_adaptation=$DEFAULT_EXTERNAL_ADAPTATION
  fi 
}



#----------------------------------------------
# APPEND PROPERTIES TO FILE
#----------------------------------------------
append_scheduler_jvm_options_to_file() {
  local jvm_options_file=${1}
  cat >> "${jvm_options_file}" << EOT
-Dcompss.scheduler=${scheduler}
-Dcompss.scheduler.config=${scheduler_config}
-Dcompss.profile.input=${input_profile}
-Dcompss.profile.output=${output_profile}
-Dcompss.project.file=${projFile}
-Dcompss.resources.file=${resFile}
-Dcompss.project.schema=${COMPSS_HOME}/Runtime/configuration/xml/projects/project_schema.xsd
-Dcompss.resources.schema=${COMPSS_HOME}/Runtime/configuration/xml/resources/resources_schema.xsd
-Dcompss.conn=${conn}
-Dcompss.external.adaptation=${external_adaptation}
EOT
}


#----------------------------------------------
# CLEAN ENV
#----------------------------------------------
clean_scheduler_env () {
  :
}
