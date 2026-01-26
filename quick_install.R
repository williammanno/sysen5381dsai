# Quick install script - run this in R or RStudio
# Copy and paste this entire block into R console

# Set CRAN mirror
options(repos = c(CRAN = "https://cran.rstudio.com/"))

# Install packages
cat("Installing usethis, gert, and credentials...\n")
install.packages(c("usethis", "gert", "credentials"), dependencies = TRUE)

# Verify installation
cat("\nChecking installation...\n")
packages <- c("usethis", "gert", "credentials")
for (pkg in packages) {
  if (requireNamespace(pkg, quietly = TRUE)) {
    cat(paste("✅", pkg, "installed successfully\n"))
  } else {
    cat(paste("❌", pkg, "failed to install\n"))
  }
}
