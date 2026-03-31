library(astr)
library(dplyr)

log_file <- snakemake@log[[1]]
con <- file(log_file, open = "wt")
sink(con, type = "output")
sink(con, type = "message")

tryCatch({
  
  raw_dir   <- snakemake@params$raw_dir
  timezone  <- snakemake@params$timezone
  cols_keep <- snakemake@params$cols_keep
  out_csv   <- snakemake@output$csv
  
  message(paste("Starting UPAS munging at", Sys.time()))
  message(paste("raw_dir:", raw_dir))

  files <- list.files(
    path       = file.path(raw_dir, "upas"),
    pattern    = "^PS.*.txt$",
    full.names = TRUE
  )
  message(paste("Found", length(files), "files:"))
  message(paste(files, collapse="\n"))
  
  df <- files %>%
    lapply(function(f) {
      message(paste("Reading:", f))
      read_ast_log(f, update_names=TRUE, tz=timezone, cols_keep=cols_keep)
    }) %>%
    bind_rows()
  
  message(paste("Combined df:", nrow(df), "rows x", ncol(df), "cols"))
  write.csv(df, out_csv, row.names=FALSE)
  message(paste("Wrote:", out_csv))
  
}, error = function(e) {
  message(paste("ERROR:", conditionMessage(e)))
  stop(e)
})

sink(type = "message")
sink(type = "output")
close(con)