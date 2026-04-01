| Relative path | Function | Description |
|---------------|----------|-------------|
| llama.cpp/convert_hf_to_gguf.py | parse_args |  |
| llama.cpp/convert_hf_to_gguf.py | split_str_to_n_bytes |  |
| llama.cpp/convert_hf_to_gguf.py | get_model_architecture |  |
| llama.cpp/convert_hf_to_gguf.py | main |  |
| llama.cpp/convert_hf_to_gguf_update.py | download_file_with_auth |  |
| llama.cpp/convert_hf_to_gguf_update.py | download_model |  |
| llama.cpp/convert_hf_to_gguf_update.py | get_existing_models |  |
| llama.cpp/convert_llama_ggml_to_gguf.py | handle_metadata |  |
| llama.cpp/convert_llama_ggml_to_gguf.py | handle_args |  |
| llama.cpp/convert_llama_ggml_to_gguf.py | main |  |
| llama.cpp/convert_lora_to_gguf.py | get_base_tensor_name |  |
| llama.cpp/convert_lora_to_gguf.py | parse_args |  |
| llama.cpp/convert_lora_to_gguf.py | load_hparams_from_hf |  |
| llama.cpp/examples/convert_legacy_llama.py | permute |  |
| llama.cpp/examples/convert_legacy_llama.py | bf16_to_fp32 |  |
| llama.cpp/examples/convert_legacy_llama.py | load_unquantized |  |
| llama.cpp/examples/convert_legacy_llama.py | merge_sharded |  |
| llama.cpp/examples/convert_legacy_llama.py | merge_multifile_models |  |
| llama.cpp/examples/convert_legacy_llama.py | permute_lazy |  |
| llama.cpp/examples/convert_legacy_llama.py | permute_part_lazy |  |
| llama.cpp/examples/convert_legacy_llama.py | part_lazy |  |
| llama.cpp/examples/convert_legacy_llama.py | pack_experts_lazy |  |
| llama.cpp/examples/convert_legacy_llama.py | lazy_load_torch_file |  |
| llama.cpp/examples/convert_legacy_llama.py | lazy_load_safetensors_file |  |
| llama.cpp/examples/convert_legacy_llama.py | must_read |  |
| llama.cpp/examples/convert_legacy_llama.py | lazy_load_file |  |
| llama.cpp/examples/convert_legacy_llama.py | bounded_parallel_map | Parallel map, but with backpressure.  If the caller doesn't call `next` fast enough, this will stop calling `func` at some point rather than letting results pile up in memory.  Specifically, there is a max of one output value buffered per thread. |
| llama.cpp/examples/convert_legacy_llama.py | check_vocab_size |  |
| llama.cpp/examples/convert_legacy_llama.py | pick_output_type |  |
| llama.cpp/examples/convert_legacy_llama.py | per_model_weight_count_estimation |  |
| llama.cpp/examples/convert_legacy_llama.py | convert_to_output_type |  |
| llama.cpp/examples/convert_legacy_llama.py | convert_model_names |  |
| llama.cpp/examples/convert_legacy_llama.py | nth_multifile_path | Given any path belonging to a multi-file model (e.g. foo.bin.1), return the nth path in the model. |
| llama.cpp/examples/convert_legacy_llama.py | find_multifile_paths | Given any path belonging to a multi-file model (e.g. foo.bin.1), return the whole list of paths in the model. |
| llama.cpp/examples/convert_legacy_llama.py | load_some_model | Load a model of any supported format. |
| llama.cpp/examples/convert_legacy_llama.py | default_convention_outfile |  |
| llama.cpp/examples/convert_legacy_llama.py | default_outfile |  |
| llama.cpp/examples/convert_legacy_llama.py | do_dump_model |  |
| llama.cpp/examples/convert_legacy_llama.py | main |  |
| llama.cpp/examples/json_schema_to_grammar.py | _build_repetition |  |
| llama.cpp/examples/json_schema_to_grammar.py | _generate_min_max_int |  |
| llama.cpp/examples/json_schema_to_grammar.py | main |  |
| llama.cpp/examples/model-conversion/scripts/causal/compare-logits.py | quick_logits_check | Lightweight sanity check before NMSE |
| llama.cpp/examples/model-conversion/scripts/causal/compare-logits.py | main |  |
| llama.cpp/examples/model-conversion/scripts/causal/run-org-model.py | parse_arguments |  |
| llama.cpp/examples/model-conversion/scripts/causal/run-org-model.py | load_model_and_tokenizer |  |
| llama.cpp/examples/model-conversion/scripts/causal/run-org-model.py | enable_torch_debugging |  |
| llama.cpp/examples/model-conversion/scripts/causal/run-org-model.py | get_prompt |  |
| llama.cpp/examples/model-conversion/scripts/causal/run-org-model.py | main |  |
| llama.cpp/examples/model-conversion/scripts/embedding/run-original-model.py | parse_arguments |  |
| llama.cpp/examples/model-conversion/scripts/embedding/run-original-model.py | load_model_and_tokenizer |  |
| llama.cpp/examples/model-conversion/scripts/embedding/run-original-model.py | get_prompt |  |
| llama.cpp/examples/model-conversion/scripts/embedding/run-original-model.py | main |  |
| llama.cpp/examples/model-conversion/scripts/utils/check-nmse.py | calculate_nmse |  |
| llama.cpp/examples/model-conversion/scripts/utils/check-nmse.py | load_logits |  |
| llama.cpp/examples/model-conversion/scripts/utils/check-nmse.py | interpret_nmse | Provide interpretation of NMSE value |
| llama.cpp/examples/model-conversion/scripts/utils/check-nmse.py | main |  |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | get_model_name_from_env_path |  |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | summarize | Print a tensor in llama.cpp debug style.  Supports: - 2D tensors (seq, hidden) - 3D tensors (batch, seq, hidden) - 4D tensors (batch, seq, heads, dim_per_head) via flattening heads × dim_per_head  Shows first and last max_vals of each vector per sequence position. |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | debug_hook |  |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | setup_rope_debug | Apply monkey patch to dump RoPE activations for debugging.  Args:     model_module_path: Path to the model module (e.g., "transformers.models.apertus.modeling_apertus")     function_name: Name of the RoPE function to patch (default: "apply_rotary_pos_emb")  Example:     from utils.common import setup_rope_debug     setup_rope_debug("transformers.models.apertus.modeling_apertus") |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | save_output_data | Save output data (logits/embeddings), tokens, and prompt to files.  Args:     data:        numpy array of floats (logits or embeddings)     tokens:      list or array of token IDs     prompt:      string containing the input prompt     model_name:  name of the model     type_suffix: optional suffix like "-embeddings" (default: "")     output_dir:  directory to save files (default: "data")  Creates the following files in output_dir:     - pytorch-{model_name}{type_suffix}.bin     - pytorch-{model_name}{type_suffix}.txt     - pytorch-{model_name}{type_suffix}-prompt.txt     - pytorch-{model_name}{type_suffix}-tokens.bin |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | compare_tokens |  |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | show_version_warning |  |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | get_model_transformers_version |  |
| llama.cpp/examples/model-conversion/scripts/utils/common.py | exit_with_warning |  |
| llama.cpp/examples/model-conversion/scripts/utils/compare_tokens.py | parse_arguments |  |
| llama.cpp/examples/model-conversion/scripts/utils/compare_tokens.py | main |  |
| llama.cpp/examples/model-conversion/scripts/utils/hf-add-model-to-collection.py | add_model_to_collection | Add a model to an existing collection  Args:     collection_slug: The slug of the collection (e.g., "username/collection-name-12345")     model_id: The model repository ID (e.g., "username/model-name")     note: Optional note about the model  Returns:     True if successful, False if failed |
| llama.cpp/examples/model-conversion/scripts/utils/hf-add-model-to-collection.py | main |  |
| llama.cpp/examples/model-conversion/scripts/utils/hf-create-collection.py | create_collection | Create a new collection on Hugging Face  Args:     title: Collection title     description: Collection description     private: Whether the collection should be private (default: False)     namespace: Optional namespace (defaults to your username)  Returns:     Collection object if successful, None if failed |
| llama.cpp/examples/model-conversion/scripts/utils/hf-create-collection.py | main |  |
| llama.cpp/examples/model-conversion/scripts/utils/hf-create-model.py | load_template_and_substitute |  |
| llama.cpp/examples/model-conversion/scripts/utils/hf-upload-gguf-model.py | upload_gguf_file | Upload a GGUF file to a Hugging Face model repository  Args:     local_file_path: Path to your local GGUF file     repo_id: Your repository ID (e.g., "username/model-name")     filename_in_repo: Optional custom name for the file in the repo |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | get_weight_map |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | get_all_tensor_names |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | find_tensor_file |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | read_safetensors_header |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | get_tensor_size_bytes |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | format_size |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | get_all_tensor_metadata |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | normalize_tensor_name |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | list_all_tensors |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | print_tensor_info |  |
| llama.cpp/examples/model-conversion/scripts/utils/inspect-org-model.py | main |  |
| llama.cpp/examples/model-conversion/scripts/utils/semantic_check.py | cosine_similarity |  |
| llama.cpp/examples/model-conversion/scripts/utils/semantic_check.py | load_embeddings_from_file |  |
| llama.cpp/examples/model-conversion/scripts/utils/semantic_check.py | test_single_prompt_similarity |  |
| llama.cpp/examples/model-conversion/scripts/utils/semantic_check.py | read_prompt_from_file |  |
| llama.cpp/examples/model-conversion/scripts/utils/semantic_check.py | main |  |
| llama.cpp/examples/pydantic_models_to_grammar.py | map_pydantic_type_to_gbnf |  |
| llama.cpp/examples/pydantic_models_to_grammar.py | format_model_and_field_name |  |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_list_rule | Generate a GBNF rule for a list of a given element type.  :param element_type: The type of the elements in the list (e.g., 'string'). :return: A string representing the GBNF rule for a list of the given type. |
| llama.cpp/examples/pydantic_models_to_grammar.py | get_members_structure |  |
| llama.cpp/examples/pydantic_models_to_grammar.py | regex_to_gbnf | Translate a basic regex pattern to a GBNF rule. Note: This function handles only a subset of simple regex patterns. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_gbnf_integer_rules | Generate GBNF Integer Rules  Generates GBNF (Generalized Backus-Naur Form) rules for integers based on the given maximum and minimum digits.  Parameters:     max_digit (int): The maximum number of digits for the integer. Default is None.     min_digit (int): The minimum number of digits for the integer. Default is None.  Returns:     integer_rule (str): The identifier for the integer rule generated.     additional_rules (list): A list of additional rules generated based on the given maximum and minimum digits. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_gbnf_float_rules | Generate GBNF float rules based on the given constraints.  :param max_digit: Maximum number of digits in the integer part (default: None) :param min_digit: Minimum number of digits in the integer part (default: None) :param max_precision: Maximum number of digits in the fractional part (default: None) :param min_precision: Minimum number of digits in the fractional part (default: None) :return: A tuple containing the float rule and additional rules as a list  Example Usage: max_digit = 3 min_digit = 1 max_precision = 2 min_precision = 1 generate_gbnf_float_rules(max_digit, min_digit, max_precision, min_precision)  Output: ('float-3-1-2-1', ['integer-part-max3-min1 ::= [0-9] [0-9] [0-9]?', 'fractional-part-max2-min1 ::= [0-9] [0-9]?', 'float-3-1-2-1 ::= integer-part-max3-min1 "." fractional-part-max2-min *1'])  Note: GBNF stands for Generalized Backus-Naur Form, which is a notation technique to specify the syntax of programming languages or other formal grammars. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_gbnf_rule_for_type | Generate GBNF rule for a given field type.  :param model_name: Name of the model.  :param field_name: Name of the field. :param field_type: Type of the field. :param is_optional: Whether the field is optional. :param processed_models: List of processed models. :param created_rules: List of created rules. :param field_info: Additional information about the field (optional).  :return: Tuple containing the GBNF type and a list of additional rules. :rtype: tuple[str, list] |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_gbnf_grammar | Generate GBnF Grammar  Generates a GBnF grammar for a given model.  :param model: A Pydantic model class to generate the grammar for. Must be a subclass of BaseModel. :param processed_models: A set of already processed models to prevent infinite recursion. :param created_rules: A dict containing already created rules to prevent duplicates. :return: A list of GBnF grammar rules in string format. And two booleans indicating if an extra markdown or triple quoted string is in the grammar. Example Usage: ``` model = MyModel processed_models = set() created_rules = dict()  gbnf_grammar = generate_gbnf_grammar(model, processed_models, created_rules) ``` |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_gbnf_grammar_from_pydantic_models | Generate GBNF Grammar from Pydantic Models.  This method takes a list of Pydantic models and uses them to generate a GBNF grammar string. The generated grammar string can be used for parsing and validating data using the generated * grammar.  Args:     models (list[type[BaseModel]]): A list of Pydantic models to generate the grammar from.     outer_object_name (str): Outer object name for the GBNF grammar. If None, no outer object will be generated. Eg. "function" for function calling.     outer_object_content (str): Content for the outer rule in the GBNF grammar. Eg. "function_parameters" or "params" for function calling.     list_of_outputs (str, optional): Allows a list of output objects Returns:     str: The generated GBNF grammar string.  Examples:     models = [UserModel, PostModel]     grammar = generate_gbnf_grammar_from_pydantic(models)     print(grammar)     # Output:     # root ::= UserModel | PostModel     # ... |
| llama.cpp/examples/pydantic_models_to_grammar.py | get_primitive_grammar | Returns the needed GBNF primitive grammar for a given GBNF grammar string.  Args:     grammar (str): The string containing the GBNF grammar.  Returns:     str: GBNF primitive grammar string. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_markdown_documentation | Generate markdown documentation for a list of Pydantic models.  Args:     pydantic_models (list[type[BaseModel]]): list of Pydantic model classes.     model_prefix (str): Prefix for the model section.     fields_prefix (str): Prefix for the fields section.     documentation_with_field_description (bool): Include field descriptions in the documentation.  Returns:     str: Generated text documentation. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_field_markdown | Generate markdown documentation for a Pydantic model field.  Args:     field_name (str): Name of the field.     field_type (type[Any]): Type of the field.     model (type[BaseModel]): Pydantic model class.     depth (int): Indentation depth in the documentation.     documentation_with_field_description (bool): Include field descriptions in the documentation.  Returns:     str: Generated text documentation for the field. |
| llama.cpp/examples/pydantic_models_to_grammar.py | format_json_example | Format a JSON example into a readable string with indentation.  Args:     example (dict): JSON example to be formatted.     depth (int): Indentation depth.  Returns:     str: Formatted JSON example string. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_text_documentation | Generate text documentation for a list of Pydantic models.  Args:     pydantic_models (list[type[BaseModel]]): List of Pydantic model classes.     model_prefix (str): Prefix for the model section.     fields_prefix (str): Prefix for the fields section.     documentation_with_field_description (bool): Include field descriptions in the documentation.  Returns:     str: Generated text documentation. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_field_text | Generate text documentation for a Pydantic model field.  Args:     field_name (str): Name of the field.     field_type (type[Any]): Type of the field.     model (type[BaseModel]): Pydantic model class.     depth (int): Indentation depth in the documentation.     documentation_with_field_description (bool): Include field descriptions in the documentation.  Returns:     str: Generated text documentation for the field. |
| llama.cpp/examples/pydantic_models_to_grammar.py | format_multiline_description | Format a multiline description with proper indentation.  Args:     description (str): Multiline description.     indent_level (int): Indentation level.  Returns:     str: Formatted multiline description. |
| llama.cpp/examples/pydantic_models_to_grammar.py | save_gbnf_grammar_and_documentation | Save GBNF grammar and documentation to specified files.  Args:     grammar (str): GBNF grammar string.     documentation (str): Documentation string.     grammar_file_path (str): File path to save the GBNF grammar.     documentation_file_path (str): File path to save the documentation.  Returns:     None |
| llama.cpp/examples/pydantic_models_to_grammar.py | remove_empty_lines | Remove empty lines from a string.  Args:     string (str): Input string.  Returns:     str: String with empty lines removed. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_and_save_gbnf_grammar_and_documentation | Generate GBNF grammar and documentation, and save them to specified files.  Args:     pydantic_model_list: List of Pydantic model classes.     grammar_file_path (str): File path to save the generated GBNF grammar.     documentation_file_path (str): File path to save the generated documentation.     outer_object_name (str): Outer object name for the GBNF grammar. If None, no outer object will be generated. Eg. "function" for function calling.     outer_object_content (str): Content for the outer rule in the GBNF grammar. Eg. "function_parameters" or "params" for function calling.     model_prefix (str): Prefix for the model section in the documentation.     fields_prefix (str): Prefix for the fields section in the documentation.     list_of_outputs (bool): Whether the output is a list of items.     documentation_with_field_description (bool): Include field descriptions in the documentation.  Returns:     None |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_gbnf_grammar_and_documentation | Generate GBNF grammar and documentation for a list of Pydantic models.  Args:     pydantic_model_list: List of Pydantic model classes.     outer_object_name (str): Outer object name for the GBNF grammar. If None, no outer object will be generated. Eg. "function" for function calling.     outer_object_content (str): Content for the outer rule in the GBNF grammar. Eg. "function_parameters" or "params" for function calling.     model_prefix (str): Prefix for the model section in the documentation.     fields_prefix (str): Prefix for the fields section in the documentation.     list_of_outputs (bool): Whether the output is a list of items.     documentation_with_field_description (bool): Include field descriptions in the documentation.  Returns:     tuple: GBNF grammar string, documentation string. |
| llama.cpp/examples/pydantic_models_to_grammar.py | generate_gbnf_grammar_and_documentation_from_dictionaries | Generate GBNF grammar and documentation from a list of dictionaries.  Args:     dictionaries (list[dict]): List of dictionaries representing Pydantic models.     outer_object_name (str): Outer object name for the GBNF grammar. If None, no outer object will be generated. Eg. "function" for function calling.     outer_object_content (str): Content for the outer rule in the GBNF grammar. Eg. "function_parameters" or "params" for function calling.     model_prefix (str): Prefix for the model section in the documentation.     fields_prefix (str): Prefix for the fields section in the documentation.     list_of_outputs (bool): Whether the output is a list of items.     documentation_with_field_description (bool): Include field descriptions in the documentation.  Returns:     tuple: GBNF grammar string, documentation string. |
| llama.cpp/examples/pydantic_models_to_grammar.py | create_dynamic_model_from_function | Creates a dynamic Pydantic model from a given function's type hints and adds the function as a 'run' method.  Args:     func (Callable): A function with type hints from which to create the model.  Returns:     A dynamic Pydantic model class with the provided function as a 'run' method. |
| llama.cpp/examples/pydantic_models_to_grammar.py | add_run_method_to_dynamic_model | Add a 'run' method to a dynamic Pydantic model, using the provided function.  Args:     model (type[BaseModel]): Dynamic Pydantic model class.     func (Callable): Function to be added as a 'run' method to the model.  Returns:     type[BaseModel]: Pydantic model class with the added 'run' method. |
| llama.cpp/examples/pydantic_models_to_grammar.py | create_dynamic_models_from_dictionaries | Create a list of dynamic Pydantic model classes from a list of dictionaries.  Args:     dictionaries (list[dict]): List of dictionaries representing model structures.  Returns:     list[type[BaseModel]]: List of generated dynamic Pydantic model classes. |
| llama.cpp/examples/pydantic_models_to_grammar.py | map_grammar_names_to_pydantic_model_class |  |
| llama.cpp/examples/pydantic_models_to_grammar.py | json_schema_to_python_types |  |
| llama.cpp/examples/pydantic_models_to_grammar.py | list_to_enum |  |
| llama.cpp/examples/pydantic_models_to_grammar.py | convert_dictionary_to_pydantic_model | Convert a dictionary to a Pydantic model class.  Args:     dictionary (dict): Dictionary representing the model structure.     model_name (str): Name of the generated Pydantic model.  Returns:     type[BaseModel]: Generated Pydantic model class. |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | create_completion | Calls the /completion API on llama-server.  See https://github.com/ggml-org/llama.cpp/tree/HEAD/tools/server#api-endpoints |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | example_rce | Minimal test case where the LLM call an arbitrary python function. |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | example_calculator | Have the LLM ask to get a calculation done.  Here the grammar gets generated by passing the available function models to generate_gbnf_grammar_and_documentation function. This also generates a documentation usable by the LLM.  pydantic_model_list is the list of pydantic models outer_object_name is an optional name for an outer object around the actual model object. Like a "function" object with "function_parameters" which contains the actual model object. If None, no outer object will be generated outer_object_content is the name of outer object content.  model_prefix is the optional prefix for models in the documentation. (Default="Output Model") fields_prefix is the prefix for the model fields in the documentation. (Default="Output Fields") |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | example_struct | A example structured output based on pydantic models.  The LLM will create an entry for a Book database out of an unstructured text. We need no additional parameters other than our list of pydantic models. |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | get_current_datetime | Get the current date and time in the given format.  Args:      output_format: formatting string for the date and time, defaults to '%Y-%m-%d %H:%M:%S' |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | get_current_weather | Get the current weather in a given location |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | example_concurrent | An example for parallel function calling with a Python function, a pydantic function model and an OpenAI like function definition. |
| llama.cpp/examples/pydantic_models_to_grammar_examples.py | main |  |
| llama.cpp/ggml/src/ggml-cuda/template-instances/generate_cu_files.py | get_short_name |  |
| llama.cpp/ggml/src/ggml-opencl/kernels/embed_kernel.py | main |  |
| llama.cpp/ggml/src/ggml-virtgpu/regenerate_remoting.py | main |  |
| llama.cpp/ggml/src/ggml-webgpu/wgsl-shaders/embed_wgsl.py | expand_includes | Replace #include "file" lines in the text with the contents of that file. Searches for files relative to input_dir. |
| llama.cpp/ggml/src/ggml-webgpu/wgsl-shaders/embed_wgsl.py | chunk_shader | Split shader_code into safe raw-string sized chunks. |
| llama.cpp/ggml/src/ggml-webgpu/wgsl-shaders/embed_wgsl.py | raw_delim | Pick a raw-string delimiter that does not appear in the shader. |
| llama.cpp/ggml/src/ggml-webgpu/wgsl-shaders/embed_wgsl.py | write_shader |  |
| llama.cpp/ggml/src/ggml-webgpu/wgsl-shaders/embed_wgsl.py | main |  |
| llama.cpp/gguf-py/examples/reader.py | read_gguf_file | Reads and prints key-value pairs and tensor information from a GGUF file in an improved format.  Parameters: - gguf_file_path: Path to the GGUF file. |
| llama.cpp/gguf-py/examples/writer.py | writer_example |  |
| llama.cpp/gguf-py/gguf/quants.py | quant_shape_to_byte_shape |  |
| llama.cpp/gguf-py/gguf/quants.py | quant_shape_from_byte_shape |  |
| llama.cpp/gguf-py/gguf/quants.py | _apply_over_grouped_rows |  |
| llama.cpp/gguf-py/gguf/quants.py | np_roundf |  |
| llama.cpp/gguf-py/gguf/quants.py | quantize |  |
| llama.cpp/gguf-py/gguf/quants.py | dequantize |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_convert_endian.py | byteswap_noop |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_convert_endian.py | byteswap_q4_0 |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_convert_endian.py | byteswap_q8_0 |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_convert_endian.py | byteswap_q4_k |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_convert_endian.py | byteswap_q6_k |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_convert_endian.py | convert_byteorder |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_convert_endian.py | main |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | get_file_host_endian |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | dump_metadata |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | dump_metadata_json |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | markdown_table_with_alignment_support |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | element_count_rounded_notation |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | translate_tensor_name |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | dump_markdown_metadata |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_dump.py | main |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_editor_gui.py | main |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_hash.py | gguf_hash |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_hash.py | main |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_new_metadata.py | get_field_data |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_new_metadata.py | find_token |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_new_metadata.py | copy_with_new_metadata |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_new_metadata.py | main |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_set_metadata.py | minimal_example |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_set_metadata.py | set_metadata |  |
| llama.cpp/gguf-py/gguf/scripts/gguf_set_metadata.py | main |  |
| llama.cpp/gguf-py/gguf/tensor_mapping.py | get_tensor_name_map |  |
| llama.cpp/gguf-py/gguf/utility.py | fill_templated_filename |  |
| llama.cpp/gguf-py/gguf/utility.py | model_weight_count_rounded_notation |  |
| llama.cpp/gguf-py/gguf/utility.py | size_label |  |
| llama.cpp/gguf-py/gguf/utility.py | naming_convention |  |
| llama.cpp/gguf-py/gguf/vocab.py | bytes_to_unicode | Returns list of utf-8 byte and a mapping to unicode strings. We specifically avoids mapping to whitespace/control characters the bpe code barfs on.  The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a significant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. |
| llama.cpp/gguf-py/tests/test_quants.py | compare_tensors |  |
| llama.cpp/gguf-py/tests/test_quants.py | do_test |  |
| llama.cpp/scripts/compare-llama-bench.py | format_flops | Format FLOPS values with appropriate units for better readability. |
| llama.cpp/scripts/compare-llama-bench.py | format_flops_for_table | Format FLOPS values for table display without unit suffix (since unit is in header). |
| llama.cpp/scripts/compare-llama-bench.py | get_flops_unit_name | Determine the best FLOPS unit name based on the magnitude of values. |
| llama.cpp/scripts/compare-logprobs.py | get_remote_corpus |  |
| llama.cpp/scripts/compare-logprobs.py | dump_logits |  |
| llama.cpp/scripts/compare-logprobs.py | get_token_logprobs |  |
| llama.cpp/scripts/compare-logprobs.py | clean_text |  |
| llama.cpp/scripts/compare-logprobs.py | compare_logits |  |
| llama.cpp/scripts/compare-logprobs.py | parse_pattern |  |
| llama.cpp/scripts/compare-logprobs.py | parse_args |  |
| llama.cpp/scripts/compare-logprobs.py | main |  |
| llama.cpp/scripts/create_ops_docs.py | main |  |
| llama.cpp/scripts/fetch_server_test_models.py | collect_hf_model_test_parameters |  |
| llama.cpp/scripts/gen-unicode-data.py | unicode_data_iter |  |
| llama.cpp/scripts/gen-unicode-data.py | out |  |
| llama.cpp/scripts/get_chat_template.py | get_chat_template |  |
| llama.cpp/scripts/get_chat_template.py | main |  |
| llama.cpp/scripts/hip/gcn-cdna-vgpr-check.py | parse_log_file |  |
| llama.cpp/scripts/hip/gcn-cdna-vgpr-check.py | main |  |
| llama.cpp/scripts/jinja/jinja-tester.py | format_template_content | Format the Jinja template content using Jinja2's lexer. |
| llama.cpp/scripts/server-bench.py | get_prompts_text |  |
| llama.cpp/scripts/server-bench.py | get_prompt_lengths_rng |  |
| llama.cpp/scripts/server-bench.py | get_prompts_rng |  |
| llama.cpp/scripts/server-bench.py | get_server |  |
| llama.cpp/scripts/server-bench.py | get_prompt_length |  |
| llama.cpp/scripts/server-bench.py | send_prompt |  |
| llama.cpp/scripts/server-bench.py | benchmark |  |
| llama.cpp/scripts/server-test-model.py | run_query |  |
| llama.cpp/scripts/server-test-model.py | test_chat |  |
| llama.cpp/scripts/server-test-model.py | test_tool_call |  |
| llama.cpp/scripts/server-test-model.py | main |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | run_cmd |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | test_install |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | run_llama_cli |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | test_llama_cli_cpu |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | test_llama_cli_gpu |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | test_llama_cli_npu |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | run_llama_bench |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | test_llama_bench_cpu |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | test_llama_bench_gpu |  |
| llama.cpp/scripts/snapdragon/qdc/tests/test_bench.py | test_llama_bench_npu |  |
| llama.cpp/scripts/tool_bench.py | scoped_server |  |
| llama.cpp/scripts/tool_bench.py | plot |  |
| llama.cpp/scripts/tool_bench.py | run |  |
| llama.cpp/scripts/verify-checksum-models.py | sha256sum |  |
| llama.cpp/tests/test-tokenizer-random.py | generator_custom_text | General tests |
| llama.cpp/tests/test-tokenizer-random.py | generator_custom_text_edge_cases | Edge cases found while debugging |
| llama.cpp/tests/test-tokenizer-random.py | generator_vocab_words | Brute force check all vocab words |
| llama.cpp/tests/test-tokenizer-random.py | generator_ascii_lr_strip |  |
| llama.cpp/tests/test-tokenizer-random.py | generator_apostrophe |  |
| llama.cpp/tests/test-tokenizer-random.py | generator_added_lr_strip |  |
| llama.cpp/tests/test-tokenizer-random.py | generator_random_added_tokens |  |
| llama.cpp/tests/test-tokenizer-random.py | generator_random_chars | Brute force random text with simple characters |
| llama.cpp/tests/test-tokenizer-random.py | generator_unicodes | Iterate unicode characters |
| llama.cpp/tests/test-tokenizer-random.py | generator_random_unicodes | Brute force random text with unicode characters |
| llama.cpp/tests/test-tokenizer-random.py | generator_random_vocab_chars | Brute force random text with vocab characters |
| llama.cpp/tests/test-tokenizer-random.py | generator_random_vocab_words | Brute force random text from vocab words |
| llama.cpp/tests/test-tokenizer-random.py | compare_tokenizers |  |
| llama.cpp/tests/test-tokenizer-random.py | main |  |
| llama.cpp/tools/mtmd/legacy-models/convert_image_encoder_to_gguf.py | k |  |
| llama.cpp/tools/mtmd/legacy-models/convert_image_encoder_to_gguf.py | should_skip_tensor |  |
| llama.cpp/tools/mtmd/legacy-models/convert_image_encoder_to_gguf.py | get_tensor_name |  |
| llama.cpp/tools/mtmd/legacy-models/convert_image_encoder_to_gguf.py | bytes_to_unicode | Returns list of utf-8 byte and a corresponding list of unicode strings. The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a significant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. And avoids mapping to whitespace/control characters the bpe code barfs on. |
| llama.cpp/tools/mtmd/legacy-models/convert_image_encoder_to_gguf.py | get_non_negative_vision_feature_layers | Determine the vision feature layer(s) for the llava model, which are indices into the hidden states of the visual encoder. Note that the hidden states array generally takes the form:      [<emb input>, <output of enc block 0>, ... <output of enc block num_hidden_layers>]  so feature indices should be offset as n+1 to get the output of encoder block n. We convert all vision feature layers to non-negative so that -1 can be used in the model as an unset value. If no vision feature layer is found, we leave it unset. |
| llama.cpp/tools/mtmd/legacy-models/glmedge-convert-image-encoder-to-gguf.py | k |  |
| llama.cpp/tools/mtmd/legacy-models/glmedge-convert-image-encoder-to-gguf.py | should_skip_tensor |  |
| llama.cpp/tools/mtmd/legacy-models/glmedge-convert-image-encoder-to-gguf.py | get_tensor_name |  |
| llama.cpp/tools/mtmd/legacy-models/glmedge-convert-image-encoder-to-gguf.py | bytes_to_unicode | Returns list of utf-8 byte and a corresponding list of unicode strings. The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a significant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. And avoids mapping to whitespace/control characters the bpe code barfs on. |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | is_safetensor_file |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | load_model |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | save_model |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | is_vision_tower |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | is_newline |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | is_mm_projector |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | newline_criteria |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | proj_criteria |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | clean_vision_tower_from_checkpoint |  |
| llama.cpp/tools/mtmd/legacy-models/llava_surgery_v2.py | find_relevant_checkpoints |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | _get_unpad_data |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | _trunc_normal_ |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | trunc_normal_tf_ | Fills the input Tensor with values drawn from a truncated normal distribution. The values are effectively drawn from the normal distribution :math:`\mathcal{N}(     ext{mean},      ext{std}^2)` with values outside :math:`[a, b]` redrawn until they are within the bounds. The method used for generating the random values works best when :math:`a \leq     ext{mean} \leq b`. NOTE: this 'tf' variant behaves closer to Tensorflow / JAX impl where the bounds [a, b] are applied when sampling the normal distribution with mean=0, std=1.0 and the result is subsequently scaled and shifted by the mean and std args. Args:     tensor: an n-dimensional `torch.Tensor`     mean: the mean of the normal distribution     std: the standard deviation of the normal distribution     a: the minimum cutoff value     b: the maximum cutoff value |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | variance_scaling_ |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | lecun_normal_ |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | default_flax_embed_init |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | add_key_str |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | should_skip_tensor |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | get_tensor_name |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | bytes_to_unicode | Returns list of utf-8 byte and a corresponding list of unicode strings. The reversible bpe codes work on unicode strings. This means you need a large # of unicode characters in your vocab if you want to avoid UNKs. When you're at something like a 10B token dataset you end up needing around 5K for decent coverage. This is a significant percentage of your normal, say, 32K bpe vocab. To avoid that, we want lookup tables between utf-8 bytes and unicode strings. And avoids mapping to whitespace/control characters the bpe code barfs on. |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | get_1d_sincos_pos_embed_from_grid | embed_dim: output dimension for each position pos: a list of positions to be encoded: size (M,) out: (M, D) |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | get_2d_sincos_pos_embed_from_grid |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | get_2d_sincos_pos_embed | grid_size: int of the grid height and width return: pos_embed: [grid_size*grid_size, embed_dim] or [1+grid_size*grid_size, embed_dim] (w/ or w/o cls_token) |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | _replace_name_resampler |  |
| llama.cpp/tools/mtmd/legacy-models/minicpmv-convert-image-encoder-to-gguf.py | _replace_name |  |
| llama.cpp/tools/mtmd/tests/test-deepseek-ocr.py | run_mtmd_deepseek_ocr | Run inference using llama.cpp mtmd-cli. |
| llama.cpp/tools/mtmd/tests/test-deepseek-ocr.py | compute_embedding_similarity | Compute cosine similarity between two texts using embedding model. |
| llama.cpp/tools/mtmd/tests/test-deepseek-ocr.py | read_expected_output | Read expected OCR output from file. |
| llama.cpp/tools/mtmd/tests/test-deepseek-ocr.py | main |  |
| llama.cpp/tools/server/bench/bench.py | main |  |
| llama.cpp/tools/server/bench/bench.py | start_benchmark |  |
| llama.cpp/tools/server/bench/bench.py | start_server |  |
| llama.cpp/tools/server/bench/bench.py | start_server_background |  |
| llama.cpp/tools/server/bench/bench.py | is_server_listening |  |
| llama.cpp/tools/server/bench/bench.py | is_server_ready |  |
| llama.cpp/tools/server/bench/bench.py | escape_metric_name |  |
| llama.cpp/tools/server/tests/conftest.py | stop_server_after_each_test |  |
| llama.cpp/tools/server/tests/conftest.py | do_something |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | test_server_start_simple |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | test_server_props |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | test_server_models |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | test_server_slots |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | test_load_split_model |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | test_no_webui |  |
| llama.cpp/tools/server/tests/unit/test_basic.py | test_server_model_aliases_and_tags |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_completion |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_completion_cached_tokens |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_completion_stream |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_completion_with_openai_library |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_template |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_template_assistant_prefill |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_apply_chat_template |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_completion_with_response_format |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_completion_with_json_schema |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_completion_with_grammar |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_invalid_chat_completion_req |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_completion_with_timings_per_token |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_logprobs |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_logprobs_stream |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_logit_bias |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_context_size_exceeded |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_context_size_exceeded_stream |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_return_progress |  |
| llama.cpp/tools/server/tests/unit/test_chat_completion.py | test_chat_completions_multiple_choices |  |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | get_test_image_base64 | Get a test image in base64 format |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | vision_server | Separate fixture for vision tests that require multimodal support |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_messages_basic | Test basic Anthropic messages endpoint |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_messages_with_system | Test messages with system prompt |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_messages_multipart_content | Test messages with multipart content blocks |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_messages_conversation | Test multi-turn conversation |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_messages_streaming | Test streaming messages |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_count_tokens | Test token counting endpoint |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_count_tokens_with_system | Test token counting with system prompt |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_count_tokens_no_max_tokens | Test that count_tokens doesn't require max_tokens |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_tool_use_basic | Test basic tool use |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_tool_result | Test sending tool results back  This test verifies that tool_result blocks are properly converted to role="tool" messages internally. Without proper conversion, this would fail with a 500 error: "unsupported content[].type" because tool_result blocks would remain in the user message content array. |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_tool_result_with_text | Test tool result mixed with text content  This tests the edge case where a user message contains both text and tool_result blocks. The server must properly split these into separate messages: a user message with text, followed by tool messages. Without proper handling, this would fail with 500: "unsupported content[].type" |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_tool_result_error | Test tool result with error flag |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_tool_streaming | Test streaming with tool use |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_vision_format_accepted | Test that Anthropic vision format is accepted (format validation only) |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_vision_base64_with_multimodal_model | Test vision with base64 image using Anthropic format with multimodal model |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_stop_sequences | Test stop_sequences parameter |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_temperature | Test temperature parameter |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_top_p | Test top_p parameter |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_top_k | Test top_k parameter (llama.cpp specific) |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_missing_messages | Test error when messages are missing |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_empty_messages | Test permissive handling of empty messages array |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_streaming_content_block_indices | Test that content block indices are correct in streaming |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_thinking | Test extended thinking parameter |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_metadata | Test metadata parameter |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_vs_openai_different_response_format | Verify Anthropic format is different from OpenAI format |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_thinking_history_in_count_tokens | Test that interleaved thinking blocks in conversation history are not dropped during conversion. |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_thinking_history_in_template | Test that reasoning_content from converted interleaved thinking blocks renders in the prompt. |
| llama.cpp/tools/server/tests/unit/test_compat_anthropic.py | test_anthropic_thinking_with_reasoning_model | Test that thinking content blocks are properly returned for reasoning models |
| llama.cpp/tools/server/tests/unit/test_compat_oai_responses.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_compat_oai_responses.py | test_responses_with_openai_library |  |
| llama.cpp/tools/server/tests/unit/test_compat_oai_responses.py | test_responses_stream_with_openai_library |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_stream |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_stream_vs_non_stream |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_with_openai_library |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_stream_with_openai_library |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_stream_with_openai_library_stops |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_consistent_result_same_seed |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_different_result_different_seed |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_consistent_result_different_batch_size |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_cache_vs_nocache_prompt |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_nocache_long_input_prompt |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_json_prompt_no_mtmd |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_json_prompt_mtm_error_when_not_supported |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_with_tokens_input |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_parallel_slots |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_unified |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_response_fields |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_n_probs |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_n_probs_stream |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_n_probs_post_sampling |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_logit_bias |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_cancel_request |  |
| llama.cpp/tools/server/tests/unit/test_completion.py | test_completion_prompt_cache |  |
| llama.cpp/tools/server/tests/unit/test_ctx_shift.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_ctx_shift.py | test_ctx_shift_enabled |  |
| llama.cpp/tools/server/tests/unit/test_ctx_shift.py | test_ctx_shift_disabled_short_prompt |  |
| llama.cpp/tools/server/tests/unit/test_ctx_shift.py | test_ctx_shift_disabled_long_prompt |  |
| llama.cpp/tools/server/tests/unit/test_ctx_shift.py | test_ctx_shift_disabled_stream |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_single |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_multiple |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_multiple_with_fa |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_mixed_input |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_pooling_mean |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_pooling_mean_multiple |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_pooling_none |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_pooling_none_oai |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_openai_library_single |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_openai_library_multiple |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_error_prompt_too_long |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_same_prompt_give_same_result |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_usage_single |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_usage_multiple |  |
| llama.cpp/tools/server/tests/unit/test_embedding.py | test_embedding_openai_library_base64 |  |
| llama.cpp/tools/server/tests/unit/test_infill.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_infill.py | test_infill_without_input_extra |  |
| llama.cpp/tools/server/tests/unit/test_infill.py | test_infill_with_input_extra |  |
| llama.cpp/tools/server/tests/unit/test_infill.py | test_invalid_input_extra_req |  |
| llama.cpp/tools/server/tests/unit/test_infill.py | test_with_qwen_model |  |
| llama.cpp/tools/server/tests/unit/test_lora.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_lora.py | test_lora |  |
| llama.cpp/tools/server/tests/unit/test_lora.py | test_lora_per_request |  |
| llama.cpp/tools/server/tests/unit/test_lora.py | test_with_big_model |  |
| llama.cpp/tools/server/tests/unit/test_proxy.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_proxy.py | test_mcp_no_proxy |  |
| llama.cpp/tools/server/tests/unit/test_proxy.py | test_mcp_proxy |  |
| llama.cpp/tools/server/tests/unit/test_proxy.py | test_mcp_proxy_custom_port |  |
| llama.cpp/tools/server/tests/unit/test_rerank.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_rerank.py | test_rerank |  |
| llama.cpp/tools/server/tests/unit/test_rerank.py | test_rerank_tei_format |  |
| llama.cpp/tools/server/tests/unit/test_rerank.py | test_invalid_rerank_req |  |
| llama.cpp/tools/server/tests/unit/test_rerank.py | test_rerank_usage |  |
| llama.cpp/tools/server/tests/unit/test_rerank.py | test_rerank_top_n |  |
| llama.cpp/tools/server/tests/unit/test_rerank.py | test_rerank_tei_top_n |  |
| llama.cpp/tools/server/tests/unit/test_router.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_router.py | test_router_chat_completion_stream |  |
| llama.cpp/tools/server/tests/unit/test_router.py | _get_model_status |  |
| llama.cpp/tools/server/tests/unit/test_router.py | _wait_for_model_status |  |
| llama.cpp/tools/server/tests/unit/test_router.py | _load_model_and_wait |  |
| llama.cpp/tools/server/tests/unit/test_router.py | test_router_unload_model |  |
| llama.cpp/tools/server/tests/unit/test_router.py | test_router_models_max_evicts_lru |  |
| llama.cpp/tools/server/tests/unit/test_router.py | test_router_no_models_autoload |  |
| llama.cpp/tools/server/tests/unit/test_router.py | test_router_api_key_required |  |
| llama.cpp/tools/server/tests/unit/test_security.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_security.py | test_access_public_endpoint |  |
| llama.cpp/tools/server/tests/unit/test_security.py | test_incorrect_api_key |  |
| llama.cpp/tools/server/tests/unit/test_security.py | test_correct_api_key |  |
| llama.cpp/tools/server/tests/unit/test_security.py | test_correct_api_key_anthropic_header |  |
| llama.cpp/tools/server/tests/unit/test_security.py | test_openai_library_correct_api_key |  |
| llama.cpp/tools/server/tests/unit/test_security.py | test_cors_options |  |
| llama.cpp/tools/server/tests/unit/test_security.py | test_local_media_file |  |
| llama.cpp/tools/server/tests/unit/test_sleep.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_sleep.py | test_server_sleep |  |
| llama.cpp/tools/server/tests/unit/test_slot_save.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_slot_save.py | test_slot_save_restore |  |
| llama.cpp/tools/server/tests/unit/test_slot_save.py | test_slot_erase |  |
| llama.cpp/tools/server/tests/unit/test_speculative.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_speculative.py | fixture_create_server |  |
| llama.cpp/tools/server/tests/unit/test_speculative.py | test_with_and_without_draft |  |
| llama.cpp/tools/server/tests/unit/test_speculative.py | test_different_draft_min_draft_max |  |
| llama.cpp/tools/server/tests/unit/test_speculative.py | test_slot_ctx_not_exceeded |  |
| llama.cpp/tools/server/tests/unit/test_speculative.py | test_with_ctx_shift |  |
| llama.cpp/tools/server/tests/unit/test_speculative.py | test_multi_requests_parallel |  |
| llama.cpp/tools/server/tests/unit/test_template.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_template.py | test_reasoning |  |
| llama.cpp/tools/server/tests/unit/test_template.py | test_date_inside_prompt |  |
| llama.cpp/tools/server/tests/unit/test_template.py | test_add_generation_prompt |  |
| llama.cpp/tools/server/tests/unit/test_tokenize.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_tokenize.py | test_tokenize_detokenize |  |
| llama.cpp/tools/server/tests/unit/test_tokenize.py | test_tokenize_with_bos |  |
| llama.cpp/tools/server/tests/unit/test_tokenize.py | test_tokenize_with_pieces |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | do_test_completion_with_required_tool_tiny |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_completion_with_required_tool_tiny_fast |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_completion_with_required_tool_tiny_slow |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_completion_with_required_tool_real_model |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | do_test_completion_without_tool_call |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_completion_without_tool_call_fast |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_completion_without_tool_call_slow |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_weather |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | do_test_weather |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_calc_result |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | do_test_calc_result |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_thoughts |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | test_hello_world |  |
| llama.cpp/tools/server/tests/unit/test_tool_call.py | do_test_hello_world |  |
| llama.cpp/tools/server/tests/unit/test_vision_api.py | get_img_url |  |
| llama.cpp/tools/server/tests/unit/test_vision_api.py | create_server |  |
| llama.cpp/tools/server/tests/unit/test_vision_api.py | test_models_supports_multimodal_capability |  |
| llama.cpp/tools/server/tests/unit/test_vision_api.py | test_v1_models_supports_multimodal_capability |  |
| llama.cpp/tools/server/tests/unit/test_vision_api.py | test_vision_chat_completion |  |
| llama.cpp/tools/server/tests/unit/test_vision_api.py | test_vision_completion |  |
| llama.cpp/tools/server/tests/unit/test_vision_api.py | test_vision_embeddings |  |
| llama.cpp/tools/server/tests/utils.py | parallel_function_calls | Run multiple functions in parallel and return results in the same order as calls. Equivalent to Promise.all in JS.  Example usage:  results = parallel_function_calls([     (func1, (arg1, arg2)),     (func2, (arg3, arg4)), ]) |
| llama.cpp/tools/server/tests/utils.py | match_regex |  |
| llama.cpp/tools/server/tests/utils.py | download_file | Download a file from a URL to a local path. If the file already exists, it will not be downloaded again.  output_file_path is the local path to save the downloaded file. If not provided, the file will be saved in the root directory.  Returns the local path of the downloaded file. |
| llama.cpp/tools/server/tests/utils.py | is_slow_test_allowed |  |
| llama.cpp/tools/tts/convert_pt_to_hf.py | flatten_state_dict |  |
| llama.cpp/tools/tts/tts-outetts.py | fill_hann_window |  |
| llama.cpp/tools/tts/tts-outetts.py | irfft |  |
| llama.cpp/tools/tts/tts-outetts.py | fold |  |
| llama.cpp/tools/tts/tts-outetts.py | process_frame |  |
| llama.cpp/tools/tts/tts-outetts.py | embd_to_audio |  |
| llama.cpp/tools/tts/tts-outetts.py | save_wav |  |
| llama.cpp/tools/tts/tts-outetts.py | process_text |  |
| nbchat/channels/whatsapp_server.py | handle_message | Process one inbound WhatsApp message and return the agent's reply. |
| nbchat/channels/whatsapp_server.py | health |  |
| nbchat/core/client.py | get_client |  |
| nbchat/core/compressor.py | _get_session |  |
| nbchat/core/compressor.py | init_session | Initialise (or reset) compression state for *session_id*. |
| nbchat/core/compressor.py | clear_session | Remove all compression state for *session_id* (call on session reset). |
| nbchat/core/compressor.py | get_compression_stats | Return a snapshot of per-tool compression statistics.  Returns a dict mapping ``tool_name`` → ``{calls, compressed_calls, compression_rate, avg_ratio, strategies}``.  ``avg_ratio < 1.0`` means output was on average compressed. ``compression_rate`` is the fraction of calls that triggered compression. |
| nbchat/core/compressor.py | reset_compression_stats | Clear all accumulated compression statistics (useful in tests). |
| nbchat/core/compressor.py | _record_stat |  |
| nbchat/core/compressor.py | _extract_key_arg | Extract the primary string argument (usually a file path) from JSON tool args.  Used as the identity key for repeat-read detection. |
| nbchat/core/compressor.py | _detect_file_extension | Detect file extension from JSON tool arguments.  Returns the extension (e.g. '.py') in lower case, or '' if undetectable. |
| nbchat/core/compressor.py | _python_skeleton | Extract an importable skeleton from Python source using the AST.  Preserves: imports, top-level assignments, function/async-function signatures (with short docstrings), class definitions with all method signatures (with short docstrings).  Function bodies are replaced with '...'.  Returns None on SyntaxError so the caller can fall back to head+tail. |
| nbchat/core/compressor.py | _json_skeleton | Summarise JSON structure: key names, value types, and counts. |
| nbchat/core/compressor.py | _yaml_skeleton | Extract top-level YAML keys without requiring PyYAML. |
| nbchat/core/compressor.py | _js_skeleton | Extract function/class/export signatures from JS/TS using regex. |
| nbchat/core/compressor.py | _syntax_aware_truncate | Dispatch to the appropriate skeleton extractor.  Returns None when no extractor applies or extraction fails — the caller should fall back to head+tail in that case. |
| nbchat/core/compressor.py | _head_tail | Symmetric head+tail truncation preserving both ends of the output. |
| nbchat/core/compressor.py | compress_tool_output | Return a compressed version of *result* bounded to MAX_TOOL_OUTPUT_CHARS.  Strategy (evaluated in priority order):  1. Short output (≤ MAX_TOOL_OUTPUT_CHARS) — pass through unchanged. 2. Session lossless set — tool was learned to be lossy; use head+tail,    skip LLM/skeleton. 3. Repeat-read detection — if this exact (tool_name, key_arg) was    compressed recently, the model is re-requesting it because the    compression lost information.  Add to session lossless set and return    head+tail immediately. 4. File-read tool + structured extension — apply syntax-aware skeleton    extraction (AST for Python, structural for JSON/YAML/JS). 5. File-read / command tool — head+tail truncation; no LLM, no relevance    filtering (filtering causes re-read loops). 6. All other tools — LLM structural compression.  Side effects:   • Compression statistics are updated for every call.   • Session lossless set may be updated on repeat-read detection.  Parameters ---------- session_id:     Pass the current session ID to enable per-session lossless learning     and repeat-read detection.  Pass "" (default) to disable both. |
| nbchat/core/config.py | _load_yaml |  |
| nbchat/core/db.py | _is_error_content | Check if content contains error indicators. |
| nbchat/core/db.py | init_db | Create tables if they do not exist. Idempotent. |
| nbchat/core/db.py | log_message |  |
| nbchat/core/db.py | log_row |  |
| nbchat/core/db.py | log_tool_msg |  |
| nbchat/core/db.py | load_history |  |
| nbchat/core/db.py | get_session_ids |  |
| nbchat/core/db.py | replace_session_history |  |
| nbchat/core/db.py | _meta_set |  |
| nbchat/core/db.py | _meta_get |  |
| nbchat/core/db.py | save_context_summary |  |
| nbchat/core/db.py | load_context_summary |  |
| nbchat/core/db.py | save_turn_summaries | Persist the full in-memory turn-summary cache for *session_id*. |
| nbchat/core/db.py | load_turn_summaries | Return the stored turn-summary cache, or {} if none exists. |
| nbchat/core/db.py | save_task_log |  |
| nbchat/core/db.py | load_task_log |  |
| nbchat/core/db.py | append_episodic | Append one tool-exchange record to the episodic store. |
| nbchat/core/db.py | query_episodic_by_entities | Return episodic entries whose entity_refs overlap with *entity_refs*.  Uses a LIKE search over the JSON-encoded entity_refs column so no JSON extension is required.  Returns rows sorted by importance_score DESC. |
| nbchat/core/db.py | query_episodic_top_importance | Return the highest-importance episodic entries for *session_id*. |
| nbchat/core/db.py | delete_episodic_for_session | Remove all episodic entries for *session_id* (used on session reset). |
| nbchat/core/db.py | get_core_memory | Return all core memory slots for *session_id* as a plain dict. |
| nbchat/core/db.py | set_core_memory_key | Upsert a single core memory slot. |
| nbchat/core/db.py | update_core_memory | Upsert multiple core memory slots in a single transaction. |
| nbchat/core/db.py | clear_core_memory | Delete all core memory entries for *session_id* (used on session reset). |
| nbchat/core/db.py | save_global_monitoring_stats | Persist cross-session monitoring aggregates to session_meta.  Uses the sentinel session_id '__global__' so no new table is required. The value is JSON-serialised and stored under key 'monitoring_global_v1'. |
| nbchat/core/db.py | load_global_monitoring_stats | Load cross-session monitoring aggregates from session_meta.  Returns the parsed dict, or None if no data has been saved yet. |
| nbchat/core/monitoring.py | parse_last_completion_metrics | Parse the most recent completed LLM call from the llama.cpp server log.  Reads the last _LOG_TAIL_BYTES from the file and extracts cache metrics for the final completion block.  Returns an invalid _CacheMetrics if the log is absent or the block cannot be parsed. |
| nbchat/core/monitoring.py | _detect_warnings |  |
| nbchat/core/monitoring.py | _empty_global |  |
| nbchat/core/monitoring.py | merge_into_global | Return a new global stats dict with session_data merged in.  Both dicts follow the shape returned by SessionMonitor.to_mergeable(). Pure function — does not mutate either argument. |
| nbchat/core/monitoring.py | get_global_report | Compute derived metrics from raw global stats.  Returns a report dict with the same structure as SessionMonitor.get_session_report() but aggregated across all sessions. |
| nbchat/core/monitoring.py | suggest_config | Return a list of concrete config change suggestions.  Each suggestion is a dict: {     "priority": "high" | "medium" | "low",     "target": "<config key or tool name>",     "action": "<what to change>",     "reason": "<evidence summary>", } |
| nbchat/core/monitoring.py | get_session_monitor | Return the SessionMonitor for *session_id*, creating it if needed. |
| nbchat/core/monitoring.py | flush_session_monitor | Merge session monitor data into global stats and persist.  Call this at the end of a session or when switching sessions. After flushing, the session monitor is removed from memory to prevent stale data.  Parameters ---------- db: the nbchat.core.db module (passed to avoid circular imports) |
| nbchat/core/monitoring.py | format_report | Return a human-readable summary of a session or global report. |
| nbchat/core/monitoring.py | format_monitoring_html | Render monitoring data as compact HTML for the sidebar widget.  Parameters ---------- session_report:     Output of SessionMonitor.get_session_report(). global_report:     Output of get_global_report(), or None if no cross-session data yet. code_color:     Hex color for code/metric values — should match CODE_COLOR in styles.py.  Layout ------ - Session cache metrics (open by default) - Per-tool rows inside a nested collapsible - Warnings always visible (not collapsed) — prominent orange text - Global stats + suggestions (collapsed by default) |
| nbchat/core/remote.py | _token | Return the GitHub PAT from the environment. |
| nbchat/core/remote.py | _remote_url | Return an HTTPS URL that contains the PAT.  Parameters ---------- repo_name:     The repository name to use in the URL.  If ``None`` the default     :data:`~nbchat.core.config.REPO_NAME` is used. |
| nbchat/core/retry.py | _is_retryable | Check if an error is retryable based on error message. |
| nbchat/core/retry.py | _calculate_delay | Calculate delay with exponential backoff and jitter. |
| nbchat/core/retry.py | retry | Decorator to add retry logic to a function.  Args:     func: Function to decorate     max_retries: Maximum number of retry attempts     initial_delay: Initial delay in seconds     max_delay: Maximum delay in seconds     backoff_multiplier: Multiplier for exponential backoff     on_retry: Optional callback when retry occurs (attempt, error, next_delay)  Returns:     Decorated function with retry logic |
| nbchat/core/retry.py | retry_with_backoff | Execute a function with retry logic and exponential backoff.  Args:     func: Function to execute     args: Positional arguments for func     max_retries: Maximum number of retry attempts     initial_delay: Initial delay in seconds     max_delay: Maximum delay in seconds     backoff_multiplier: Multiplier for exponential backoff     on_retry: Optional callback when retry occurs     kwargs: Keyword arguments for func  Returns:     Result of func  Raises:     Exception: If all retries fail |
| nbchat/core/utils.py | lazy_import | Import a module only when needed.  The function mirrors the behaviour of the legacy ``lazy_import``. |
| nbchat/tools/__init__.py | _generate_schema |  |
| nbchat/tools/__init__.py | get_tools | Return the list of tools formatted for chat.completions.create. |
| nbchat/tools/browser.py | _hint |  |
| nbchat/tools/browser.py | _err | Return a JSON error envelope.  Callers may supply a custom hint; otherwise one is derived from the message text via _hint(). Extra keyword arguments are merged into the response dict. |
| nbchat/tools/browser.py | browser | Stateless browser tool. Launches a fresh Chromium instance per call.  Parameters ---------- url:     The page to visit. Must include scheme (https://...). A missing scheme     is auto-corrected to https://. actions:     Optional list of interactions performed *before* content extraction.     Supported types:      - ``{"type": "click",      "selector": "CSS"}``     - ``{"type": "type",       "selector": "CSS", "text": "value"}``       Empty string is valid (clears the field). Key must be present.     - ``{"type": "select",     "selector": "CSS", "value": "option"}``     - ``{"type": "wait",       "selector": "CSS"}``     - ``{"type": "wait",       "timeout": 2000}``     - ``{"type": "scroll",     "direction": "down"|"up", "amount": 500}``       ``amount`` is always treated as positive; ``direction`` controls sign.     - ``{"type": "navigate",   "url": "https://..."}``       HTTP errors and timeouts on navigate are treated as action errors.     - ``{"type": "screenshot", "path": "file.png"}``      Action errors are non-fatal: logged in ``action_errors``, ``status``     set to ``"partial"``, and execution continues with the next action. selector:     CSS selector to scope text extraction to one element. When set, ``title``     is omitted from the response. Omit for full-page extraction. extract_elements:     When True, include ``interactive`` (buttons, inputs, links) and ``links``     in the response — useful for discovering what actions are available. navigation_timeout:     Milliseconds to wait for page navigation (default 30 000). action_timeout:     Milliseconds to wait for each action's selector/interaction (default 5 000). max_content_length:     Maximum characters of page text returned (default 8 000). wait_until:     Playwright navigation event — one of ``"commit"``, ``"domcontentloaded"``     (default, fastest), ``"load"``, or ``"networkidle"`` (slowest).  Returns ------- str     Always valid JSON. On success::          {             "status": "success" | "partial",             "url": "https://...",             "title": "...",          # omitted when selector= is set             "content": "...",             "actions": [...],        # omitted when no actions were given             "action_errors": [...],  # omitted when all actions succeeded             "interactive": [...],    # included when extract_elements=True             "links": [...]           # included when extract_elements=True         }      On failure::          {"error": "...", "hint": "..."} |
| nbchat/tools/create_file.py | _safe_resolve | Resolve ``rel_path`` against ``repo_root`` and ensure the result does **not** escape the repository root (prevents directory traversal). |
| nbchat/tools/create_file.py | _create_file | Create a new file at ``path`` (relative to the repository root) with the supplied ``content``.  Parameters ---------- path     File path relative to the repo root.  ``path`` may contain     directory separators but **must not** escape the root. content     Raw text to write into the file.  Returns ------- str     JSON string.  On success:      .. code-block:: json          { "result": "File created: <path>" }      On failure:      .. code-block:: json          { "error": "<exception message>" } |
| nbchat/tools/get_weather.py | _geocode_city | Return latitude and longitude for a given city name.  The function queries the OpenMeteo geocoding API and returns the first result.  It raises a :class:`ValueError` if the city cannot be found. |
| nbchat/tools/get_weather.py | _fetch_weather | Fetch current and daily forecast weather data for the given coordinates and date.  Parameters ---------- lat, lon: float     Latitude and longitude of the location. date: str     ISO 8601 formatted date string (YYYY-MM-DD).  The API expects a     single day, so ``start_date`` and ``end_date`` are identical. |
| nbchat/tools/get_weather.py | _get_weather | Retrieve current and forecast weather information for a given city and date.  Parameters ---------- city: str     The name of the city to look up. date: str, optional     The date for which to retrieve forecast data (ISO format YYYY-MM-DD).     If omitted or empty, today's date is used. |
| nbchat/tools/make_change_to_file.py | _safe_resolve | Resolve ``rel_path`` against ``repo_root`` and guard against directory traversal. Normalize to NFKC to ensure characters like '..' or '/' aren't spoofed |
| nbchat/tools/make_change_to_file.py | _extract_payload |  |
| nbchat/tools/make_change_to_file.py | apply_diff |  |
| nbchat/tools/make_change_to_file.py | _trim_overlap | Trims the end of ins_lines if they already exist at the start of following_lines. Prevents duplicate 'stitching' when the diff and file overlap. |
| nbchat/tools/make_change_to_file.py | _normalize_diff_lines | Clean the diff and strip Unified Diff metadata headers. |
| nbchat/tools/make_change_to_file.py | _detect_newline |  |
| nbchat/tools/make_change_to_file.py | _is_done |  |
| nbchat/tools/make_change_to_file.py | _read_str |  |
| nbchat/tools/make_change_to_file.py | _parse_create_diff |  |
| nbchat/tools/make_change_to_file.py | _parse_update_diff |  |
| nbchat/tools/make_change_to_file.py | _advance_cursor |  |
| nbchat/tools/make_change_to_file.py | _read_section |  |
| nbchat/tools/make_change_to_file.py | _equals_slice | Helper to compare a slice of lines using a transformation function (like strip). |
| nbchat/tools/make_change_to_file.py | _find_context |  |
| nbchat/tools/make_change_to_file.py | _apply_chunks |  |
| nbchat/tools/make_change_to_file.py | make_change_to_file | Apply a unified diff to a file inside the repository.  Parameters ---------- path : str     Relative file path (under the repo root). op_type : str     One of ``create``, ``update`` or ``delete``. diff : str     Unified diff string (ignored for ``delete``).  Returns ------- str     JSON string with either ``result`` or ``error``. |
| nbchat/tools/push_to_github.py | push_to_github | Push the current repository to GitHub.  Parameters ---------- commit_message:     Commit message for the auto commit.  Defaults to ``"Auto commit"``. rebase:     Whether to rebase during pull.  Defaults to ``False`` to mirror     the original behaviour. |
| nbchat/tools/repo_overview.py | walk_python_files | Return a sorted list of all ``.py`` files under *root*. |
| nbchat/tools/repo_overview.py | extract_functions_from_file | Return a list of (function_name, docstring) for top‑level functions.  Functions defined inside classes or other functions are ignored. |
| nbchat/tools/repo_overview.py | build_markdown_table |  |
| nbchat/tools/repo_overview.py | func | Generate a markdown table of all top‑level Python functions.  The table is written to ``repo_overview.md`` in the repository root. |
| nbchat/tools/run_command.py | _safe_resolve | Resolve ``rel_path`` against ``repo_root`` and ensure the result does **not** escape the repository root (prevents directory traversal). |
| nbchat/tools/run_command.py | _run_command | Execute ``command`` in the repository root and return a JSON string with:     * ``stdout``     * ``stderr``     * ``exit_code`` Any exception is converted to an error JSON.  The ``cwd`` argument is accepted for backward compatibility but ignored; the command is always executed in the repository root. |
| nbchat/tools/run_tests.py | _run_tests | Execute `pytest -q` in the repository root and return JSON. |
| nbchat/tools/send_email.py | _send_email | Send an email via Gmail.  Parameters ---------- subject: str     Subject line of the email. body: str     Plain‑text body of the email.  Returns ------- str     JSON string containing either ``result`` or ``error``. |
| nbchat/tools/test_browser.py | ok |  |
| nbchat/tools/test_browser.py | err |  |
| nbchat/tools/test_browser.py | _make_playwright_mock |  |
| nbchat/tools/test_browser.py | _patch |  |
| nbchat/tools/test_browser.py | _run | Convenience: run browser() with a mock and return (data, page). |
| nbchat/ui/chat_builder.py | build_messages | Build OpenAI messages from internal chat history.  Parameters ---------- history:     List of canonical 6-tuples:     ``(role, content, tool_id, tool_name, tool_args, error_flag)``.     Should already be pre-windowed (via _window()) to the last N user     turns.  Leading ``("system", …)`` rows (L1/L2/prior context blocks     injected by ContextMixin._window()) are extracted and placed into     the volatile context turn rather than messages[0]. system_prompt:     The static system message.  Written verbatim to ``messages[0]``     and never modified — this is the contract that enables KV caching. task_log:     Optional list of recent action strings maintained by ChatUI.     Included in the volatile context turn (messages[1]) so the model     always knows what it has been doing even when old messages are     outside the window.  Message layout -------------- messages[0]  {"role": "system",    "content": system_prompt}  <- static messages[1]  {"role": "user",      "content": "[SESSION CONTEXT]..."}  <- volatile messages[2]  {"role": "assistant", "content": "Context received."}     <- volatile messages[3+] actual conversation turns (user / assistant / tool)  messages[1] and messages[2] are omitted when there is no volatile content (empty task_log and no leading system rows in history), keeping the message list minimal for fresh sessions.  Notes ----- Many local-model servers (llama.cpp, Ollama, ...) enforce via their Jinja chat template that the *system* role may only appear as the very first message.  This function never emits more than one system-role message. Any ``("system", …)`` rows that appear *after* conversation content (which should not occur in normal operation but may surface in legacy DB rows) are demoted to user-role ``[CONTEXT NOTE]`` messages.  ``("analysis", …)`` rows are reasoning traces — display-only, never sent to the model. |
| nbchat/ui/chat_renderer.py | render_user |  |
| nbchat/ui/chat_renderer.py | render_assistant |  |
| nbchat/ui/chat_renderer.py | render_reasoning |  |
| nbchat/ui/chat_renderer.py | render_tool |  |
| nbchat/ui/chat_renderer.py | render_assistant_with_tools |  |
| nbchat/ui/chat_renderer.py | render_assistant_full |  |
| nbchat/ui/chat_renderer.py | render_system |  |
| nbchat/ui/chat_renderer.py | render_placeholder |  |
| nbchat/ui/chat_renderer.py | render_compacted_summary |  |
| nbchat/ui/context_manager.py | _parse_structured_summary | Parse a GOAL/ENTITIES/RATIONALE structured summary into a dict. |
| nbchat/ui/context_manager.py | _extract_entities | Extract entity references (file paths, API paths, URLs) from *text*.  Returns a deduplicated list capped at 10 entries. |
| nbchat/ui/context_manager.py | _group_by_user_turn | Split *rows* into per-user-turn groups. |
| nbchat/ui/conversation.py | _is_error_content | Return True if *content* contains common error signal keywords. |
| nbchat/ui/conversation.py | _normalise_args | Return a canonical JSON string for stall-detection comparison.  Sorts keys so that argument dicts with identical content but different key ordering compare equal, preventing the stall detector from missing repeated calls when the model varies key order across turns. |
| nbchat/ui/conversation.py | _sanitize_messages | Normalize assistant messages for strict OpenAI-compat models.  The OpenAI spec requires content=None (not "") when tool_calls are present on an assistant message.  Smaller models fail to emit structured tool calls on subsequent turns when they see content="" alongside tool_calls in their history.  This sanitizer fixes both freshly built messages and old DB rows reconstructed via assistant_full. |
| nbchat/ui/styles.py | _style |  |
| nbchat/ui/styles.py | _div |  |
| nbchat/ui/styles.py | _style_code | Inject color style into un-styled <code>, <span>, and codehilite <div> tags. |
| nbchat/ui/styles.py | _md |  |
| nbchat/ui/styles.py | _tool_calls_html |  |
| nbchat/ui/styles.py | user_message_html |  |
| nbchat/ui/styles.py | assistant_message_html |  |
| nbchat/ui/styles.py | reasoning_html |  |
| nbchat/ui/styles.py | assistant_full_html |  |
| nbchat/ui/styles.py | assistant_message_with_tools_html |  |
| nbchat/ui/styles.py | tool_result_html |  |
| nbchat/ui/styles.py | system_message_html |  |
| nbchat/ui/styles.py | compacted_summary_html |  |
| nbchat/ui/styles.py | make_widget | Return an :class:`ipywidgets.HTML` widget.  The original code defined this function inside ``compacted_summary_html`` due to a stray indentation.  That made the module fail to import.  The function is now defined at module level. |
| nbchat/ui/tool_executor.py | run_tool | Execute a tool with arguments and return the (trimmed) string result.  Includes retry policy inspired by openclaw (https://docs.openclaw.ai/concepts/retry). |
| nbchat/ui/utils.py | md_to_html | Convert markdown to HTML using fenced code blocks.  This is the same implementation that lived in the legacy file. |
| nbchat/ui/utils.py | changed_files |  |
| run.py | _run_blocking | Standard blocking run for setup tasks. |
| run.py | _run_detached | Launches a command fully detached from the parent process. Returns the PID of the started process. |
| run.py | _is_port_free |  |
| run.py | _wait_for |  |
| run.py | _save_service_info |  |
| run.py | _load_service_info |  |
| run.py | _kill_pid |  |
| run.py | main |  |
| run.py | status |  |
| run.py | stop |  |
| tests/test_chat_builder.py | _row | Convenience factory for canonical 6-tuples. |
| tests/test_compressor.py | _mock_client |  |
| tests/test_compressor.py | _short |  |
| tests/test_compressor.py | _long |  |
| tests/test_context_manager.py | _row |  |
| tests/test_context_manager.py | _make_config |  |
| tests/test_context_manager.py | _patched_window |  |
| tests/test_debug_path.py | test_debug |  |
| tests/test_monitoring.py | _make_log | Write a fake llama.cpp log containing one completion block. |
| tests/test_simple_import.py | test_imports_work | Test that all imports work |