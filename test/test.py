from crypto_utils import generate_keys, encrypt_message, decrypt_message ,save_keys ,load_private_key ,load_public_key ,serialize_public_key ,encrypt_file , decrypt_file

test_text= "hi am test cryptography"

# test to generate keys
private_key, public_key = generate_keys()
print("Private Key:", private_key)
print("Public Key:", public_key)

# test to encrypt and decrypt a message
encrypted_message = encrypt_message(public_key, test_text)
print("Encrypted Message:", encrypted_message)

decrypted_message = decrypt_message(private_key, encrypted_message)
print("Decrypted Message:", decrypted_message)

# test to save and load keys
save_keys(private_key, public_key)
loaded_private_key = load_private_key()
loaded_public_key = load_public_key()
print("Loaded Private Key:", loaded_private_key)
print("Loaded Public Key:", loaded_public_key)  

# test to serialize public key
serialized_public_key = serialize_public_key(public_key)
print("Serialized Public Key:", serialized_public_key)

# test to encrypt and decrypt a message using loaded keys
encrypted_message_loaded = encrypt_message(loaded_public_key, test_text)
print("Encrypted Message with Loaded Public Key:", encrypted_message_loaded)

decrypted_message_loaded = decrypt_message(loaded_private_key, encrypted_message_loaded)
print("Decrypted Message with Loaded Private Key:", decrypted_message_loaded)

# test to encrypt and decrypt a message using serialized public key
from crypto_utils import deserialize_public_key
deserialized_public_key = deserialize_public_key(serialized_public_key)
encrypted_message_serialized = encrypt_message(deserialized_public_key, test_text)
print("Encrypted Message with Deserialized Public Key:", encrypted_message_serialized)

decrypted_message_serialized = decrypt_message(loaded_private_key, encrypted_message_serialized)
print("Decrypted Message with Loaded Private Key:", decrypted_message_serialized)

# test to encrypt and decrypt a file
file_path = "test_file.txt"
# Create a test file
with open(file_path, "w") as f:
    f.write(test_text)


encrypt_file(public_key, file_path)
with open(file_path + ".enc", "rb") as f:
    encrypted_file_data = f.read()
print("Encrypted File Data:", encrypted_file_data)

decrypt_file(private_key, file_path + ".enc")


