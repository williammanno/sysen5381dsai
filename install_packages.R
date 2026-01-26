# R Package Installation Script
# This script helps diagnose and install required packages

# Function to check if a package is installed
check_package <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    cat(paste("❌", pkg, "is NOT installed\n"))
    return(FALSE)
  } else {
    cat(paste("✅", pkg, "is installed\n"))
    return(TRUE)
  }
}

# Check system dependencies (macOS specific)
cat("=== Checking System Dependencies ===\n")
if (.Platform$OS.type == "unix" && Sys.info()["sysname"] == "Darwin") {
  cat("macOS detected. Checking for libgit2...\n")
  cat("If gert fails to install, you may need to run:\n")
  cat("  brew install libgit2\n")
  cat("\n")
}

# Check current R version
cat("=== R Version Info ===\n")
cat("R version:", R.version.string, "\n")
cat("\n")

# Check CRAN mirror
cat("=== CRAN Mirror ===\n")
cat("Current CRAN mirror:", getOption("repos"), "\n")
cat("\n")

# Try to install packages with error handling
cat("=== Installing Packages ===\n")
packages <- c("usethis", "gert", "credentials")

for (pkg in packages) {
  cat(paste("\n--- Installing", pkg, "---\n"))
  
  if (!check_package(pkg)) {
    tryCatch({
      # Try installing from CRAN
      install.packages(pkg, dependencies = TRUE, repos = "https://cran.rstudio.com/")
      if (check_package(pkg)) {
        cat(paste("✅ Successfully installed", pkg, "\n"))
      } else {
        cat(paste("❌ Failed to install", pkg, "\n"))
      }
    }, error = function(e) {
      cat(paste("❌ Error installing", pkg, ":\n"))
      cat(paste("   ", conditionMessage(e), "\n"))
      
      # Special handling for gert
      if (pkg == "gert") {
        cat("\n⚠️  gert installation often fails due to missing system dependencies.\n")
        cat("   On macOS, try:\n")
        cat("   1. Install libgit2: brew install libgit2\n")
        cat("   2. Then re-run this script\n")
        cat("   Or install gert from source:\n")
        cat("   install.packages('gert', type = 'source')\n")
      }
    })
  } else {
    cat(paste("✅", pkg, "already installed\n"))
  }
}

cat("\n=== Final Status ===\n")
all_installed <- all(sapply(packages, check_package))
if (all_installed) {
  cat("\n✅ All packages successfully installed!\n")
} else {
  cat("\n❌ Some packages failed to install. See errors above.\n")
}
