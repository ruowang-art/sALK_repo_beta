parse_arguments <- function(args) {
  values <- list()
  index <- 1

  while (index <= length(args)) {
    key <- args[[index]]
    if (key == "--quiet-diagnostics") {
      values[["quiet_diagnostics"]] <- TRUE
      index <- index + 1
      next
    }

    if (!startsWith(key, "--") || index == length(args)) {
      stop("Invalid argument sequence near: ", key)
    }

    values[[substring(key, 3)]] <- args[[index + 1]]
    index <- index + 2
  }

  values
}

required_argument <- function(values, name) {
  value <- values[[name]]
  if (is.null(value) || !nzchar(value)) {
    stop("Missing required argument --", name)
  }
  value
}

main <- function() {
  args <- parse_arguments(commandArgs(trailingOnly = TRUE))
  translation_script <- normalizePath(
    required_argument(args, "translation-script"),
    mustWork = TRUE
  )
  input_path <- normalizePath(required_argument(args, "input"), mustWork = TRUE)
  output_path <- required_argument(args, "output")
  output_parent <- dirname(output_path)

  if (!dir.exists(output_parent)) {
    dir.create(output_parent, recursive = TRUE, showWarnings = FALSE)
  }

  translation_environment <- new.env(parent = globalenv())
  source(translation_script, local = translation_environment, chdir = FALSE)

  translate_function <- translation_environment$translate_transnetyx_file
  if (!is.function(translate_function)) {
    stop(
      "The configured translation script does not expose ",
      "translate_transnetyx_file(input_path, output_path, print_diagnostics)."
    )
  }

  translate_function(
    input_path = input_path,
    output_path = output_path,
    print_diagnostics = !isTRUE(args[["quiet_diagnostics"]])
  )

  if (!file.exists(output_path)) {
    stop("Translation function returned without creating: ", output_path)
  }
}

tryCatch(
  main(),
  error = function(error) {
    message("AutoMouse R wrapper error: ", conditionMessage(error))
    quit(save = "no", status = 1L, runLast = FALSE)
  }
)

