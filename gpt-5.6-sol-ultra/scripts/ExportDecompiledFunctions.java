// Export selected functions as Ghidra decompiler C.
// @category Haversine

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

public class ExportDecompiledFunctions extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            throw new IllegalArgumentException(
                "usage: ExportDecompiledFunctions.java OUTPUT [REGEX ...]");
        }

        File output = new File(args[0]);
        List<Pattern> patterns = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            patterns.add(Pattern.compile(args[i]));
        }

        DecompInterface decompiler = new DecompInterface();
        DecompileOptions options = new DecompileOptions();
        decompiler.setOptions(options);
        decompiler.toggleCCode(true);
        decompiler.toggleSyntaxTree(true);
        decompiler.setSimplificationStyle("decompile");

        if (!decompiler.openProgram(currentProgram)) {
            throw new IllegalStateException(
                "could not open program: " + decompiler.getLastMessage());
        }

        int matched = 0;
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(output))) {
            writer.write("PROGRAM: " + currentProgram.getName() + "\n\n");
            FunctionIterator functions =
                currentProgram.getFunctionManager().getFunctions(true);
            while (functions.hasNext() && !monitor.isCancelled()) {
                Function function = functions.next();
                String name = function.getName();
                boolean include = patterns.isEmpty();
                for (Pattern pattern : patterns) {
                    if (pattern.matcher(name).find()) {
                        include = true;
                        break;
                    }
                }
                if (!include) {
                    continue;
                }

                writer.write("/* ============================================================\n");
                writer.write(" * " + name + " @ " + function.getEntryPoint() + "\n");
                writer.write(" * signature: " + function.getSignature() + "\n");
                writer.write(" * ============================================================ */\n");

                DecompileResults result =
                    decompiler.decompileFunction(function, 120, monitor);
                if (result.decompileCompleted() &&
                    result.getDecompiledFunction() != null) {
                    writer.write(result.getDecompiledFunction().getC());
                } else {
                    writer.write("/* DECOMPILE FAILED: " +
                        result.getErrorMessage() + " */\n");
                }
                writer.write("\n\n");
                writer.flush();
                matched++;
            }
        } finally {
            decompiler.dispose();
        }
        println("Exported " + matched + " functions to " + output);
    }
}
