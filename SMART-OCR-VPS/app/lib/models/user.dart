/// Authenticated user model.
class AppUser {
  final String username;
  final String token;
  final String role;

  const AppUser({
    required this.username,
    required this.token,
    this.role = 'clinician',
  });
}
