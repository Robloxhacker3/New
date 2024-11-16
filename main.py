import subprocess
import os
import zipfile
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# Directory to store temporary files
TEMP_DIR = "/tmp/lua_to_dylib_temp"

def compile_lua_to_dylib(lua_code: str, output_path: str):
    try:
        # Write Lua code to a C file for compilation
        temp_lua_file = os.path.join(TEMP_DIR, "lua_wrapper.c")
        os.makedirs(TEMP_DIR, exist_ok=True)

        with open(temp_lua_file, "w") as f:
            f.write(f'''
#include <lua.hpp>
extern "C" {{
    int luaopen_lua_code(lua_State *L) {{
        const char* lua_script = R"({lua_code})";
        if (luaL_dostring(L, lua_script) != LUA_OK) {{
            luaL_error(L, "Error in Lua script: %s", lua_tostring(L, -1));
        }}
        return 0;
    }}
}}''')

        # Compile C file into a .dylib
        dylib_file = output_path
        compile_command = [
            "g++", "-shared", "-o", dylib_file, temp_lua_file, "-I/usr/local/include", "-L/usr/local/lib", "-llua"
        ]
        
        subprocess.run(compile_command, check=True)
        print(f"Successfully compiled to: {dylib_file}")
        os.remove(temp_lua_file)
        return dylib_file
    except subprocess.CalledProcessError as e:
        print(f"Error during compilation: {e}")
        return None

def sign_dylib(dylib_path: str, certificate_identifier: str):
    try:
        # Sign the .dylib using the provided certificate identifier
        subprocess.run(["codesign", "--sign", certificate_identifier, dylib_path], check=True)
        print(f"Successfully signed the dylib: {dylib_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error signing the dylib: {e}")
        return False

def create_zip_with_dylib(dylib_path: str, output_zip: str):
    try:
        # Create a zip file containing the dylib
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(dylib_path, os.path.basename(dylib_path))
        print(f"Created zip: {output_zip}")
        os.remove(dylib_path)
    except Exception as e:
        print(f"Error creating zip: {e}")

def process_lua_to_dylib(lua_code: str, output_zip: str, certificate_identifier: str):
    dylib_path = compile_lua_to_dylib(lua_code, os.path.join(TEMP_DIR, "generated_library.dylib"))
    
    if dylib_path is None:
        return {"error": "Failed to compile the Lua code into a dylib."}
    
    if not sign_dylib(dylib_path, certificate_identifier):
        return {"error": "Failed to sign the dylib."}
    
    create_zip_with_dylib(dylib_path, output_zip)
    return {"success": output_zip}

@app.route('/generate-dylib', methods=['POST'])
def generate_dylib():
    try:
        # Receive Lua code from the frontend
        lua_code = request.form['lua_code']
        certificate_identifier = "Developer ID Application: YourName (XXXXXXXXXX)"  # Replace with your actual certificate ID

        output_zip = "/tmp/lua_dylib_package.zip"
        result = process_lua_to_dylib(lua_code, output_zip, certificate_identifier)

        if 'error' in result:
            return jsonify(result), 400
        
        return send_file(result['success'], as_attachment=True)
    
    except Exception as e:
        print(f"Server error: {e}")
        return jsonify({"error": "Server error during processing."}), 500

if __name__ == "__main__":
    app.run(debug=True)
