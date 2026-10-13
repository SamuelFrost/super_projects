require "test_helper"

class RegistrationsControllerTest < ActionDispatch::IntegrationTest
  test "new" do
    get new_registration_path
    assert_response :success
  end

  test "create signs in the new user" do
    assert_difference -> { User.count }, 1 do
      post registration_path, params: {
        user: {
          email_address: "new-user@example.com",
          password: "password",
          password_confirmation: "password"
        }
      }
    end

    assert_redirected_to root_path
    follow_redirect!
    assert_response :success
    assert_match "new-user@example.com", response.body
    assert cookies[:session_id]
  end

  test "create rejects mismatched passwords" do
    assert_no_difference -> { User.count } do
      post registration_path, params: {
        user: {
          email_address: "new-user@example.com",
          password: "password",
          password_confirmation: "different"
        }
      }
    end

    assert_response :unprocessable_entity
  end

  test "a created user can sign in after signing out" do
    post registration_path, params: {
      user: {
        email_address: "return-user@example.com",
        password: "password",
        password_confirmation: "password"
      }
    }
    delete session_path

    post session_path, params: { email_address: "return-user@example.com", password: "password" }

    assert_redirected_to root_path
    follow_redirect!
    assert_match "return-user@example.com", response.body
  end
end
